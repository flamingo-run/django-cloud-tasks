import json

from django.http import JsonResponse
from django.views import View

from sample_app import models
from sample_app.tasks import PublishPersonTask


class PersonCreateView(View):
    def post(self, request, *args, **kwargs):
        person = models.Person.objects.create(**json.loads(request.body))
        PublishPersonTask.sync(obj=person)
        return JsonResponse(status=201, data={"status": "published"})
