import json
from typing import Dict

from django.apps import apps
from django.http import HttpResponse
from django.views.generic import View

from gcp_pilot.pubsub import Message


class GoogleCloudTaskView(View):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.tasks = self._get_available_tasks()

    def _get_available_tasks(self):
        app = apps.get_app_config('django_cloud_tasks')
        all_tasks = app.on_demand_tasks.copy()
        all_tasks.update(app.periodic_tasks.copy())
        return all_tasks

    def post(self, request, task_name, *args, **kwargs):
        try:
            task_class = self.tasks[task_name]
            data = self._parse_task_args(body=request.body)
            output, status = task_class().execute(data=data)
            if status == 200:
                result = {'result': output}
            else:
                result = {'error': output}
        except KeyError:
            status = 404
            result = {
                'error': f"Task {task_name} not found",
                'available_tasks': list(self.tasks)
            }

        response = HttpResponse(status=status, content=json.dumps(result), content_type='application/json')
        return response

    def _parse_task_args(self, body: str) -> Dict:
        return json.loads(body)


# More info: https://cloud.google.com/pubsub/docs/push#receiving_messages
class GoogleCloudSubscribeView(GoogleCloudTaskView):
    def _get_available_tasks(self):
        return apps.get_app_config('django_cloud_tasks').subscriber_tasks.copy()

    def _parse_task_args(self, body: str) -> Dict:
        return Message.load(body=body).data
