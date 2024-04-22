import json
from django.db import transaction

from django.http import JsonResponse
from django.views import View

from sample_app import models


class PersonCreateView(View):
    def post(self, request, *args, **kwargs):
        person = models.Person(**json.loads(request.body))
        person.save()
        return JsonResponse(status=201, data={"status": "published", "pk": person.pk})


class PersonReplaceView(View):
    @transaction.atomic
    def post(self, request, *args, **kwargs):
        payload = json.loads(request.body)
        person_to_replace_id = payload.pop("person_to_replace_id")

        to_delete = models.Person.objects.get(pk=person_to_replace_id)
        to_delete.delete()

        person = models.Person(**payload)
        person.save()
        return JsonResponse(status=201, data={"status": "published", "pk": person.pk})
