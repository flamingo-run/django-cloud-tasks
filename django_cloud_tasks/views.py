import json
from typing import Dict, Any

from django.apps import apps
from django.http import HttpResponse
from django.views.generic import View


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
        except KeyError:
            status = 404
            result = {
                'error': f"Task {task_name} not found",
                'available_tasks': list(self.tasks)
            }
            return self._prepare_response(status=status, payload=result)

        output, status = task_class().execute(request_body=request.body)
        if status == 200:
            result = {'result': output}
        else:
            result = {'error': output}

        return self._prepare_response(status=status, payload=result)

    def _prepare_response(self, status: int, payload: Dict[str, Any]):
        return HttpResponse(status=status, content=json.dumps(payload), content_type='application/json')


# More info: https://cloud.google.com/pubsub/docs/push#receiving_messages
class GoogleCloudSubscribeView(GoogleCloudTaskView):
    def _get_available_tasks(self):
        return apps.get_app_config('django_cloud_tasks').subscriber_tasks.copy()
