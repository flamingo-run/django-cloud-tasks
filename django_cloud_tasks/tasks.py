from abc import ABC, abstractmethod

from django.apps import apps
from django.urls import reverse

from django_cloud_tasks.client import CloudTasksClient


class Task(ABC):
    @abstractmethod
    def run(self, **kwargs):
        raise NotImplementedError()

    def execute(self, data):
        try:
            output = self.run(**data)
            success = True
        except Exception as e:  # pylint: disable=broad-except
            output = str(e)
            success = False
        return output, success

    def delay(self, **kwargs):
        payload = kwargs

        return self.__client.push(
            name=self.name(),
            queue=self.queue,
            url=self.url(),
            payload=payload,
        )

    @classmethod
    def name(cls):
        return cls.__name__

    @property
    def queue(self):
        return 'tasks'

    @classmethod
    def url(cls):
        domain = apps.get_app_config('django_cloud_tasks').domain
        path = reverse('tasks-endpoint', args=(cls.name(),))
        return f'{domain}{path}'

    @property
    def __client(self):
        return CloudTasksClient()
