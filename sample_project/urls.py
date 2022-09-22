from django.urls import include, path

urlpatterns = [
    path("", include("django_cloud_tasks.urls")),
]
