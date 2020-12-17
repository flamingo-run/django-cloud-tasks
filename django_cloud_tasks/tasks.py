import json
from abc import ABC, abstractmethod
from typing import Dict

from asgiref.sync import async_to_sync
from django.apps import apps
from django.urls import reverse
from gcp_pilot.scheduler import CloudScheduler
from gcp_pilot.tasks import CloudTasks
from gcp_pilot.pubsub import CloudSubscriber, CloudPublisher

import settings


class Task(ABC):
    _url_name = 'tasks-endpoint'

    @abstractmethod
    def run(self, **kwargs):
        raise NotImplementedError()

    def execute(self, data):
        output = self.run(**data)
        status = 200
        return output, status

    async def delay(self, **kwargs):
        if getattr(settings, 'EAGER_TASKS', False):
            return self.run(**kwargs)

        payload = kwargs

        return await self.__client.push(
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

    async def delay(self, **kwargs):
        if getattr(settings, 'EAGER_TASKS', False):
            return self.run(**kwargs)

        payload = kwargs

        return await self.__client.put(
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
    def run(self, message, metadata):
        raise NotImplementedError()

    async def delay(self, **kwargs):
        return await self.__client.create_subscription(
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
    use_async_publish = False

    def run(self, topic_name: str, message: Dict, attributes: Dict = None):
        return async_to_sync(self.__client.publish)(
            message=json.dumps(message),
            topic_id=topic_name,
            attributes=attributes,
        )

    async def delay(self, topic_name: str, message: Dict, attributes: Dict = None):
        if self.use_async_publish:
            # perform asynchronous publish to PubSub, with overhead in:
            # - publishing the message as Task
            # - receiving it through the endpoint
            # - and the finally publishing to PubSub
            # might be useful to use the Cloud Task throttling
            return super().delay(topic_name=topic_name, message=message, attributes=attributes)
        return await self.run(topic_name=topic_name, message=message, attributes=attributes)

    async def initialize(self, topic_name):
        await self.__client.create_topic(
            topic_id=topic_name,
        )

    @property
    def __client(self):
        return CloudPublisher()
