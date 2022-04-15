from django.urls import path

from swpeople import views

app_name = "swpeople"

urlpatterns = [
    path('', views.GetPeople.as_view(), name="get_people"),
    path('get_people_details/<int:id>', views.GetPeopleDetails.as_view(), name="get_people_details"),
    path('fetch/', views.FetchPeople.as_view(), name="fetch_people"),
]
