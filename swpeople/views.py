import os

import petl as etl
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.views.generic import ListView, View

from swapi.settings import BASE_DIR
from .bootstrap import people_service
from .models import FileMetaData


class GetPeople(ListView):
    model = FileMetaData
    ordering = ['-created_at']
    template_name = "swpeople/index.html"
    context_object_name = 'objs'


class FetchPeople(View):
    _people_service = people_service

    def get(self, request, *args, **kwargs):
        self._people_service.fetch_people()
        return redirect("swpeople:get_people")


class GetPeopleDetails(View):
    template_name = "swpeople/details.html"
    _people_service = people_service

    def get(self, request, *args, **kwargs):
        request_get = dict(request.GET)
        file_meta_data = self._people_service.get_file_meta_data(kwargs["id"])

        if file_meta_data.id != request.session.get("file_id"):
            request.session.flush()
            request.session["file_id"] = file_meta_data.id
        if (rows := request.session.get("rows")) and request.GET.get("load_more"):
            rows += 10
        else:
            rows = 10
        request.session["rows"] = rows

        file_path = os.path.join(BASE_DIR, "files")
        table = etl.fromcsv(os.path.join(file_path, file_meta_data.filename))
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            filter_params = request_get.get("filter_names[]")
            if filter_params:
                table = etl.aggregate(table, key=tuple(filter_params), aggregation=len, value=tuple(filter_params))
                table = etl.rename(table, "value", "count")
                table = etl.dicts(etl.rowslice(table, rows))

                html = render_to_string(self.template_name,
                                        {"table": table, "table_headers": table[0].keys(), "obj": file_meta_data})
                return HttpResponse(html)
        table = etl.dicts(etl.rowslice(table, rows))

        return render(request, self.template_name,
                      {"table": table, "table_headers": table[0].keys(), "obj": file_meta_data})
