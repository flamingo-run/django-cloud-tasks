import json
from abc import abstractmethod
from typing import Dict

from django.apps import apps
from django.conf import settings
from django.urls import reverse
from gcp_pilot.exceptions import DeletedRecently
from gcp_pilot.pubsub import CloudSubscriber, CloudPublisher
from gcp_pilot.scheduler import CloudScheduler
from gcp_pilot.tasks import CloudTasks

from django_cloud_tasks.helpers import run_coroutine


class TaskMeta(type):
    def __new__(cls, name, bases, attrs):
        app = apps.get_app_config('django_cloud_tasks')
        attrs['_app_name'] = app.app_name
        attrs['_delimiter'] = app.delimiter

        klass = type.__new__(cls, name, bases, attrs)
        if getattr(klass, 'abstract', False) and 'abstract' not in attrs:
            setattr(klass, 'abstract', False)  # TODO Removing the attribute would be better
        TaskMeta._register_task(app=app, task_class=klass)
        return klass

    def __call__(cls, *args, **kwargs):
        if cls.__name__ not in ['Task', 'PeriodicTask', 'SubscriberTask']:
            return super().__call__(*args, **kwargs)
        raise NotImplementedError(f"Do not instantiate a {cls.__name__}. Inherit and create your own.")

    @staticmethod
    def _register_task(app, task_class):
        if task_class.__name__ not in ['Task', 'PeriodicTask', 'SubscriberTask']:
            app.register_task(task_class=task_class)


class Task(metaclass=TaskMeta):
    _url_name = 'tasks-endpoint'

    @abstractmethod
    def run(self, **kwargs):
        raise NotImplementedError()

    def execute(self, data):
        output = self.run(**data)
        status = 200
        return output, status

    def delay(self, **kwargs):
        if getattr(settings, 'EAGER_TASKS', False):
            return self.run(**kwargs)

        payload = kwargs

        try:
            return run_coroutine(
                handler=self.__client.push,
                task_name=self.name(),
                queue_name=self.queue,
                url=self.url(),
                payload=json.dumps(payload),
            )
        except DeletedRecently:
            # If the task queue was "accidentally" removed, GCP does not let us recreate it in 1 week
            # so we'll use a temporary queue (defined in settings) for some time
            backup_queue_name = apps.get_app_config('django_cloud_tasks').get_backup_queue_name(
                original_name=self.queue,
            )
            if not backup_queue_name:
                raise

            return run_coroutine(
                handler=self.__client.push,
                task_name=self.name(),
                queue_name=backup_queue_name,
                url=self.url(),
                payload=json.dumps(payload),
            )

    @classmethod
    def name(cls):
        return cls.__name__

    @property
    def queue(self):
        return self._app_name or 'tasks'

    @classmethod
    def url(cls):
        domain = apps.get_app_config('django_cloud_tasks').domain
        path = reverse(cls._url_name, args=(cls.name(),))
        return f'{domain}{path}'

    @property
    def __client(self):
        return CloudTasks()


class PeriodicTask(Task):
    @abstractmethod
    def run(self, **kwargs):
        raise NotImplementedError()

    run_every = None

    def delay(self, **kwargs):
        if getattr(settings, 'EAGER_TASKS', False):
            return self.run(**kwargs)

        payload = kwargs

        return run_coroutine(
            handler=self.__client.put,
            name=self.schedule_name,
            url=self.url(),
            payload=json.dumps(payload),
            cron=self.run_every,
        )

    @property
    def schedule_name(self):
        if self._app_name:
            return f'{self._app_name}{self._delimiter}{self.name()}'
        return self.name()

    @property
    def __client(self):
        return CloudScheduler()


class SubscriberTask(Task):
    abstract = True
    _use_oidc_auth = True
    _url_name = 'subscriptions-endpoint'

    @abstractmethod
    def run(self, message, attributes):
        raise NotImplementedError()

    def delay(self, **kwargs):
        return run_coroutine(
            handler=self.__client.create_or_update_subscription,
            topic_id=self.topic_name,
            subscription_id=self.subscription_name,
            push_to_url=self.url(),
            use_oidc_auth=self._use_oidc_auth,
        )

    @property
    @abstractmethod
    def topic_name(self):
        raise NotImplementedError()

    @property
    def subscription_name(self):
        return f'{self.topic_name}{self._delimiter}{self._app_name or self.name()}'

    @property
    def __client(self):
        return CloudSubscriber()


class PublisherTask(Task):
    publish_immediately = False

    def run(self, topic_name: str, message: Dict, attributes: Dict[str, str] = None):
        return run_coroutine(
            handler=self.__client.publish,
            message=json.dumps(message),
            topic_id=self._full_topic_name(name=topic_name),
            attributes=attributes,
        )

    def delay(self, topic_name: str, message: Dict, attributes: Dict[str, str] = None):
        if self.publish_immediately:
            # perform asynchronous publish to PubSub, with overhead in:
            # - publishing the message as Task
            # - receiving it through the endpoint
            # - and the finally publishing to PubSub
            # might be useful to use the Cloud Task throttling
            full_topic_name = self._full_topic_name(name=topic_name)
            return super().delay(topic_name=full_topic_name, message=message, attributes=attributes)
        return self.run(topic_name=topic_name, message=message, attributes=attributes)

    def initialize(self, topic_name):
        run_coroutine(
            handler=self.__client.create_topic,
            topic_id=self._full_topic_name(name=topic_name),
        )

    def _full_topic_name(self, name):
        if self._app_name:
            return f'{self._app_name}{self._delimiter}{name}'
        return name

    @property
    def __client(self):
        return CloudPublisher()
