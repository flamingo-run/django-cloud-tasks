import json

from django.apps import apps
from django.http import HttpResponse
from django.views.generic import View


class GoogleCloudTaskView(View):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.tasks = apps.get_app_config('django_cloud_tasks').tasks

    def post(self, request, task_name, *args, **kwargs):
        try:
            task_class = self.tasks[task_name]
            data = json.loads(request.body)
            output, success = task_class().execute(data=data)
            if success:
                status = 200
                result = {'result': output}
            else:
                status = 400
                result = {'error': output}
        except KeyError:
            status = 404
            result = {'error': f"Task {task_name} not found"}

        response = HttpResponse(status=status, content=json.dumps(result), content_type='application/json')
        return response
