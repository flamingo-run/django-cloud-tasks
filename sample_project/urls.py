from django.urls import include, path

from sample_app import views

urlpatterns = [
    path("", include("django_cloud_tasks.urls")),
    path("create-person", views.PersonCreateView.as_view()),
    path("replace-person", views.PersonReplaceView.as_view()),
]
