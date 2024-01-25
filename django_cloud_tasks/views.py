import logging
from typing import Type, Any

from django.apps import apps
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View
from gcp_pilot.base import DEFAULT_SERVICE_ACCOUNT
from gcp_pilot.pubsub import Message
from google.auth.transport import requests
from google.oauth2 import id_token

from django_cloud_tasks import exceptions
from django_cloud_tasks.exceptions import TaskNotFound
from django_cloud_tasks.serializers import deserialize
from django_cloud_tasks.tasks import Task, SubscriberTask
from django_cloud_tasks.tasks.task import TaskMetadata


logger = logging.getLogger("django_cloud_tasks")


def verify_oidc_token(request: HttpRequest):
    auth_header: str = request.headers.get("Authorization")

    if not auth_header:
        raise PermissionDenied("No auth header")

    auth_type, creds = auth_header.split(" ", 1)
    if auth_type.capitalize() != "Bearer":
        raise PermissionDenied("Wrong auth_type " + auth_type)

    claims = id_token.verify_token(creds, requests.Request())
    if claims['email'] != DEFAULT_SERVICE_ACCOUNT:
        raise PermissionDenied("Unauthorised user " + claims['user'])


class GoogleCloudTaskView(View):
    @method_decorator(csrf_exempt)
    def post(self, request, task_name, *args, **kwargs):
        verify_oidc_token(request)
        
        try:
            task_class = self.get_task(name=task_name)
        except TaskNotFound:
            result = {"error": f"Task {task_name} not found"}
            return JsonResponse(status=404, data=result)

        task_kwargs = self.parse_input(request=request, task_class=task_class)
        task_metadata = self.parse_metadata(request=request)
        try:
            output = self.execute_task(task_class=task_class, task_metadata=task_metadata, task_kwargs=task_kwargs)
            status = "executed"
            status_code = 200
        except exceptions.DiscardTaskException:
            output = None
            status = "discarded"
            status_code = 202

        data = {"result": output, "status": status}
        try:
            return JsonResponse(status=status_code, data=data)
        except TypeError:
            logger.warning(f"Unable to serialize task output from {request.path}: {str(output)}")
            return JsonResponse(status=status_code, data={"result": str(output), "status": "executed"})

    def get_task(self, name: str) -> Type[Task]:
        app = apps.get_app_config("django_cloud_tasks")
        return app.get_task(name=name)

    def execute_task(self, task_class: type[Task], task_metadata: TaskMetadata, task_kwargs: dict) -> Any:
        return task_class(metadata=task_metadata).process(**task_kwargs)

    def parse_input(self, request, task_class: Type[Task]) -> dict:
        return deserialize(value=request.body)

    def parse_metadata(self, request) -> TaskMetadata:
        return TaskMetadata.from_headers(headers=dict(request.headers))


# More info: https://cloud.google.com/pubsub/docs/push#receiving_messages
class GoogleCloudSubscribeView(GoogleCloudTaskView):
    def parse_input(self, request, task_class: Type[SubscriberTask]) -> dict:
        message = Message.load(body=request.body, parser=task_class.message_parser())
        return {
            "content": message.data,
            "attributes": message.attributes,
        }

    def get_task(self, name: str) -> Type[SubscriberTask]:
        app = apps.get_app_config("django_cloud_tasks")
        try:
            return app.subscriber_tasks[name]
        except KeyError:
            raise TaskNotFound(name=name)

    def execute_task(self, task_class: type[SubscriberTask], task_metadata: TaskMetadata, task_kwargs: dict) -> Any:
        if task_class.use_cloud_tasks and not task_class.eager():
            metadata = task_class.push(task_kwargs=task_kwargs, headers=task_metadata.custom_headers)
            return {"cloud-tasks-forwarded": {"queue_name": metadata.queue_name, "task_id": metadata.task_id}}
        else:
            return super().execute_task(task_class=task_class, task_metadata=task_metadata, task_kwargs=task_kwargs)
