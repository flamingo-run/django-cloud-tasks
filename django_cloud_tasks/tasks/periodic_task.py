# pylint: disable=no-member
from abc import abstractmethod

from django.conf import settings
from gcp_pilot.scheduler import CloudScheduler

from django_cloud_tasks.serializers import deserialize, serialize
from django_cloud_tasks.tasks.task import Task


class PeriodicTask(Task):
    run_every = None

    @abstractmethod
    def run(self, **kwargs):
        raise NotImplementedError()

    def schedule(self, **kwargs):
        payload = serialize(kwargs)

        if getattr(settings, "EAGER_TASKS", False):
            return self.run(**deserialize(payload))

        return self.__client.put(
            name=self.schedule_name,
            url=self.url(),
            payload=payload,
            cron=self.run_every,
        )

    @property
    def schedule_name(self):
        if self._app_name:
            return f"{self._app_name}{self._delimiter}{self.name()}"
        return self.name()

    @property
    def __client(self):
        return CloudScheduler()
