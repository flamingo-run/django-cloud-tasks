import json
from abc import ABC, abstractmethod
from typing import Dict

from django.apps import apps
from django.conf import settings
from django.urls import reverse
from gcp_pilot.pubsub import CloudSubscriber, CloudPublisher
from gcp_pilot.scheduler import CloudScheduler
from gcp_pilot.tasks import CloudTasks

from django_cloud_tasks.helpers import run_coroutine


class Task(ABC):
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

        return run_coroutine(
            handler=self.__client.push,
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
        path = reverse(cls._url_name, args=(cls.name(),))
        return f'{domain}{path}'

    @property
    def __client(self):
        return CloudTasks()


class PeriodicTask(Task, ABC):
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
        return self.name()

    @property
    def __client(self):
        return CloudScheduler()


class PubSubTaskMixin:
    _use_oidc_auth = True
    _url_name = 'subscriptions-endpoint'

    @property
    @abstractmethod
    def topic_name(self):
        raise NotImplementedError()


class SubscriberTask(PubSubTaskMixin, Task, ABC):
    @abstractmethod
    def run(self, message, attributes):
        raise NotImplementedError()

    def delay(self, **kwargs):
        return run_coroutine(
            handler=self.__client.create_subscription,
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
        return self.name()

    @property
    def __client(self):
        return CloudSubscriber()


class PublisherTask(Task, ABC):
    publish_immediately = False

    def run(self, topic_name: str, message: Dict, attributes: Dict[str, str] = None):
        return run_coroutine(
            handler=self.__client.publish,
            message=json.dumps(message),
            topic_id=topic_name,
            attributes=attributes,
        )

    def delay(self, topic_name: str, message: Dict, attributes: Dict[str, str] = None):
        if self.publish_immediately:
            # perform asynchronous publish to PubSub, with overhead in:
            # - publishing the message as Task
            # - receiving it through the endpoint
            # - and the finally publishing to PubSub
            # might be useful to use the Cloud Task throttling
            return super().delay(topic_name=topic_name, message=message, attributes=attributes)
        return self.run(topic_name=topic_name, message=message, attributes=attributes)

    def initialize(self, topic_name):
        run_coroutine(
            handler=self.__client.create_topic,
            topic_id=topic_name,
        )

    @property
    def __client(self):
        return CloudPublisher()
