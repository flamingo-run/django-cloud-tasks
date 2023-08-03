import logging
from typing import Type, Any

from django.apps import apps
from django.http import JsonResponse
from django.views.generic import View
from gcp_pilot.pubsub import Message

from django_cloud_tasks import exceptions
from django_cloud_tasks.exceptions import TaskNotFound
from django_cloud_tasks.serializers import deserialize
from django_cloud_tasks.tasks import Task, SubscriberTask
from django_cloud_tasks.tasks.task import TaskMetadata


logger = logging.getLogger("django_cloud_tasks")


class GoogleCloudTaskView(View):
    def post(self, request, task_name, *args, **kwargs):
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
