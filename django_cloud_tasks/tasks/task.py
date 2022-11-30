# pylint: disable=no-member
from abc import abstractmethod
from datetime import datetime, timedelta
from functools import lru_cache
from random import randint

from django.apps import apps
from django.conf import settings
from django.urls import reverse
from django.utils.timezone import now
from gcp_pilot.exceptions import DeletedRecently
from gcp_pilot.tasks import CloudTasks

from django_cloud_tasks.serializers import deserialize, serialize


class TaskMeta(type):
    def __new__(cls, name, bases, attrs):
        app = apps.get_app_config("django_cloud_tasks")
        attrs["_app_name"] = app.app_name
        attrs["_delimiter"] = app.delimiter

        klass = type.__new__(cls, name, bases, attrs)
        if getattr(klass, "abstract", False) and "abstract" not in attrs:
            setattr(klass, "abstract", False)  # TODO Removing the attribute would be better
        TaskMeta._register_task(app=app, task_class=klass)
        return klass

    def __call__(cls, *args, **kwargs):
        if cls.__name__ not in ["Task", "PeriodicTask", "SubscriberTask"]:
            return super().__call__(*args, **kwargs)
        raise NotImplementedError(f"Do not instantiate a {cls.__name__}. Inherit and create your own.")

    @staticmethod
    def _register_task(app, task_class):
        if task_class.__name__ not in ["Task", "PeriodicTask", "SubscriberTask"]:
            app.register_task(task_class=task_class)


class Task(metaclass=TaskMeta):
    _url_name = "tasks-endpoint"
    only_once = False

    @abstractmethod
    def run(self, **kwargs):
        raise NotImplementedError()

    def _body_to_kwargs(self, request_body):
        data = deserialize(request_body)
        return data

    def execute(self, request_body):
        task_kwargs = self._body_to_kwargs(request_body=request_body)
        output = self.run(**task_kwargs)
        return output

    # Celery-compatible signature
    def delay(self, queue: str | None = None, **kwargs):
        return self._send(
            task_kwargs=kwargs,
            queue=queue,
        )

    def asap(self, **kwargs):
        return self._send(
            task_kwargs=kwargs,
        )

    def later(self, when, queue=None, **kwargs):
        if isinstance(when, int):
            delay_in_seconds = when
        elif isinstance(when, timedelta):
            delay_in_seconds = when.total_seconds()
        elif isinstance(when, datetime):
            delay_in_seconds = (when - now()).total_seconds()
        else:
            raise ValueError(f"Unsupported schedule {when} of type {when.__class__.__name__}")

        return self._send(
            task_kwargs=kwargs,
            api_kwargs=dict(delay_in_seconds=int(delay_in_seconds)),
            queue=queue,
        )

    def until(self, max_date, queue=None, **kwargs):
        if not isinstance(max_date, datetime):
            raise ValueError("max_date must be a datetime")
        if max_date < now():
            raise ValueError("max_date must be in the future")

        max_seconds = (max_date - now()).total_seconds()
        delay_in_seconds = randint(0, int(max_seconds))
        return self._send(
            task_kwargs=kwargs,
            api_kwargs=dict(delay_in_seconds=delay_in_seconds),
            queue=queue,
        )

    def _send(self, task_kwargs: dict, api_kwargs: dict | None = None, queue: str | None = None):
        payload = serialize(task_kwargs)

        if getattr(settings, "EAGER_TASKS", False):
            return self.run(**deserialize(payload))

        api_kwargs = api_kwargs or {}
        api_kwargs.update(
            dict(
                queue_name=queue or self.queue,
                url=self.url(),
                payload=payload,
            )
        )

        if self.only_once:
            api_kwargs.update(
                dict(
                    task_name=self.name(),
                    unique=False,
                )
            )

        try:
            return self.__client.push(**api_kwargs)
        except DeletedRecently:
            # If the task queue was "accidentally" removed, GCP does not let us recreate it in 1 week
            # so we'll use a temporary queue (defined in settings) for some time
            backup_queue_name = apps.get_app_config("django_cloud_tasks").get_backup_queue_name(
                original_name=self.queue,
            )
            if not backup_queue_name:
                raise

            api_kwargs["queue_name"] = backup_queue_name
            return self.__client.push(**api_kwargs)

    @classmethod
    def name(cls):
        return cls.__name__

    @property
    def queue(self):
        return self._app_name or "tasks"

    @classmethod
    def url(cls):
        domain = apps.get_app_config("django_cloud_tasks").domain
        path = reverse(cls._url_name, args=(cls.name(),))
        return f"{domain}{path}"

    @property
    def __client(self):
        return self.__get_client()

    @classmethod
    @lru_cache()
    def __get_client(cls):
        return CloudTasks()
