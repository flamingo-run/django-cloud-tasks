from django.urls import path

from django_cloud_tasks import views

urlpatterns = [
    path(r'tasks/<task_name>', views.GoogleCloudTaskView.as_view(), name='tasks-endpoint'),
]
