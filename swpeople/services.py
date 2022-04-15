import concurrent.futures as cf
import os
import typing as t
from datetime import datetime

import petl as etl
import requests
from requests import HTTPError

from swapi.settings import BASE_DIR
from .models import FileMetaData

SWAPI_API_URL = "https://swapi.dev/api"


class SwPeopleService:

    @staticmethod
    def get_file_meta_data(obj_id: int) -> FileMetaData:
        return FileMetaData.objects.get(id=obj_id)

    @staticmethod
    def create_file_meta_data(filename: str) -> FileMetaData:
        return FileMetaData.objects.create(filename=filename)

    def _fetch_objects_in_parallel(self, endpoint: str) -> t.List[dict]:
        obj_list = []
        try:
            response = requests.get(f'{SWAPI_API_URL}/{endpoint}')
            response.raise_for_status()
            json_resp = response.json()
            obj_list.extend(json_resp.get("results", []))
        except HTTPError as e:
            # Properly log error
            raise e

        results_count = len(json_resp.get("results", 0))
        total_count = response.json().get("count", 0)
        if results_count and total_count:
            num_pages = total_count // results_count
            if total_count % results_count != 0:
                # if there is any remainder from division, it means that there is an extra page.
                num_pages += 1

            urls = [f"{SWAPI_API_URL}/{endpoint}?page={i}" for i in range(2, num_pages + 1)]
            with cf.ThreadPoolExecutor(max_workers=8) as executor:
                # Start the load operations and mark each future with its URL
                future_to_url = {executor.submit(self.__load_urls, url, 15): url for url in urls}
                for future in cf.as_completed(future_to_url):
                    url = future_to_url[future]
                    try:
                        data = future.result()
                        obj_list.extend(data.get("results"))
                    except Exception as exc:
                        print('%r generated an exception: %s' % (url, exc))  # logger.error
                        raise exc
                    else:
                        print('%r page is %d bytes' % (url, len(data)))  # logger.info

        return obj_list

    def fetch_people(self) -> None:
        people_list = self._fetch_objects_in_parallel(endpoint="people")

        table = etl.fromdicts(people_list, header=people_list[0].keys())
        table = self.__transform_data(table)
        basename = "people"
        suffix = datetime.now().strftime("%y%m%d_%H%M%S")
        file_path = os.path.join(BASE_DIR, "files")
        filename = f'{"_".join([basename, suffix])}.csv'
        etl.tocsv(table, os.path.join(file_path, filename))
        SwPeopleService.create_file_meta_data(filename)

    def __fetch_planets(self) -> t.Dict[str, str]:
        planet_results = self._fetch_objects_in_parallel(endpoint="planets")
        return {plt["url"]: plt["name"] for plt in planet_results}

    def __transform_data(self, table: t.Any) -> t.Any:
        """
        edited = "2014-12-20T21:17:56.891000Z"
        date = edited.split("T")[0]
        is also another solution to convert edited.
        """
        planet_map = self.__fetch_planets()
        table = etl.addfield(table, 'date',
                             lambda rec: str(datetime.strptime(rec["edited"], "%Y-%m-%dT%H:%M:%S.%fZ").date())
                             )
        # removing the unnecessary columns
        table = etl.cutout(table, 'films', 'species', 'vehicles', 'starships', 'created')
        # transforming planet url to planet name
        return etl.convert(table, 'homeworld', planet_map)

    def __load_urls(self, url: str, timeout: int) -> t.Dict:
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
        except HTTPError as e:
            # Properly log error
            raise e
        return response.json()
