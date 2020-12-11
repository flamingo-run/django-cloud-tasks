import base64
import json
from typing import Dict

from django.apps import apps
from django.http import HttpResponse
from django.views.generic import View


class GoogleCloudTaskView(View):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.tasks = self._get_available_tasks()

    def _get_available_tasks(self):
        return apps.get_app_config('django_cloud_tasks').tasks

    def post(self, request, task_name, *args, **kwargs):
        try:
            task_class = self.tasks[task_name]
            data = json.loads(request.body)
            output, status = task_class().execute(data=data)
            if status == 200:
                result = {'result': output}
            else:
                result = {'error': output}
        except KeyError:
            status = 404
            result = {'error': f"Task {task_name} not found"}

        response = HttpResponse(status=status, content=json.dumps(result), content_type='application/json')
        return response

    def _parse_task_args(self, body: str) -> Dict:
        return json.loads(body)


# More info: https://cloud.google.com/pubsub/docs/push#receiving_messages
class GoogleCloudSubscribeView(GoogleCloudTaskView):
    def _get_available_tasks(self):
        return apps.get_app_config('django_cloud_tasks').subscribers

    def _parse_task_args(self, body: str) -> Dict:
        event = super()._parse_task_args(body=body)

        task_args = {}
        if 'data' in event:
            task_args['message'] = json.loads(base64.b64decode(event['data']).decode('utf-8'))
        task_args['metadata'] = event.get('attributes', {})
        return task_args
