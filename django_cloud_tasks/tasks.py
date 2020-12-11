import json
from abc import ABC, abstractmethod

from django.apps import apps
from django.urls import reverse
from gcp_pilot import CloudScheduler, CloudTasks


class Task(ABC):
    @abstractmethod
    def run(self, **kwargs):
        raise NotImplementedError()

    def execute(self, data):
        output = self.run(**data)
        status = 200
        return output, status

    def delay(self, **kwargs):
        payload = kwargs

        return self.__client.push(
            task_name=self.name(),
            queue_name=self.queue,
            url=self.url(),
            payload=json.dumps(payload),
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
        return CloudTasks()


class PeriodicTask(Task, ABC):
    run_every = None

    def delay(self, **kwargs):
        payload = kwargs

        return self.__client.put(
            name=self.schedule_name,
            url=self.url(),
            payload=json.dumps(payload),
            cron=self.run_every,
        )

    @property
    def schedule_name(self):
        return self.name()

    @property
    def __client(self):
        return CloudScheduler()
