import abc
from dataclasses import dataclass
from typing import Type

from cachetools.func import lru_cache
from django.apps import apps
from django.db.models import Model
from django.db import transaction
from gcp_pilot.pubsub import CloudPublisher

from django_cloud_tasks.apps import DjangoCloudTasksAppConfig
from django_cloud_tasks.context import get_current_headers
from django_cloud_tasks.serializers import serialize
from django_cloud_tasks.tasks.task import Task, get_config


class PublisherTask(Task, abc.ABC):
    # Just a specialized Task that publishes a message to PubSub
    # Since it cannot accept any random parameters, all its signatures have fixed arguments
    @classmethod
    def sync(cls, message: dict, attributes: dict[str, str] | None = None):
        return cls().run(message=message, attributes=attributes)

    @classmethod
    def asap(cls, message: dict, attributes: dict[str, str] | None = None):
        task_kwargs = {
            "message": message,
            "attributes": attributes,
        }
        return cls.push(task_kwargs=task_kwargs)

    def run(self, message: dict, attributes: dict[str, str] | None = None, headers: dict[str, str] | None = None):
        # Cloud PubSub does not support headers, but we simulate them with a key in the data property
        message = self._build_message_with_headers(message=message, headers=headers)

        return self._get_publisher_client().publish(
            message=serialize(value=message),
            topic_id=self.topic_name(),
            attributes=attributes,
        )

    def _build_message_with_headers(self, message: dict, headers: dict | None = None):
        message = message.copy()
        headers = get_current_headers() | (headers or {})
        if headers:
            message[self._app.propagated_headers_key] = headers
        return message

    @classmethod
    def set_up(cls) -> None:
        cls._get_publisher_client().create_topic(topic_id=cls.topic_name())

    @classmethod
    def topic_name(cls) -> str:
        name = cls.name()
        if app_name := get_config(name="app_name"):
            delimiter = get_config(name="delimiter")
            name = f"{app_name}{delimiter}{name}"
        return name

    @classmethod
    @lru_cache()
    def _get_publisher_client(cls) -> CloudPublisher:
        return CloudPublisher()

    @property
    @lru_cache()
    def _app(self) -> DjangoCloudTasksAppConfig:
        return apps.get_app_config("django_cloud_tasks")


@dataclass
class PreparedModelPublication:
    """Stores the information needed to publish a model to PubSub.

    Because models are mutable objects, in case we don't want to publish the event right away,
    we need to store the information needed to publish right away.
    """

    task_klass: Type["ModelPublisherTask"]
    message: dict
    attributes: dict[str, str]
    topic_name: str

    def get_task_kwargs(self):
        return {
            "message": self.message,
            "attributes": self.attributes,
            "topic_name": self.topic_name,
        }

    def sync(self):
        return self.task_klass().run(**self.get_task_kwargs())

    def asap(self):
        return self.push()

    def push(self, **kwargs):
        return self.task_klass._push_prepared(prepared=self, **kwargs)


class ModelPublisherTask(PublisherTask, abc.ABC):
    # Just a specialized Task that publishes a Django model to PubSub
    # Since it cannot accept any random parameters, all its signatures have fixed arguments
    @classmethod
    def sync(cls, obj: Model, **kwargs):
        return cls.prepare(obj=obj, **kwargs).sync()

    @classmethod
    def sync_on_commit(cls, obj: Model, **kwargs):
        prepared_publication = cls.prepare(obj=obj, **kwargs)
        transaction.on_commit(lambda: prepared_publication.sync())

    @classmethod
    def asap(cls, obj: Model, **kwargs):
        return cls.prepare(obj=obj, **kwargs).asap()

    @classmethod
    def push(cls, task_kwargs: dict, **kwargs):
        return cls.prepare(**task_kwargs).push(**kwargs)

    @classmethod
    def _push_prepared(cls, prepared: PreparedModelPublication, **kwargs):
        return super().push(task_kwargs=prepared.get_task_kwargs(), **kwargs)

    @classmethod
    def prepare(cls, obj: Model, **kwargs):
        return PreparedModelPublication(
            task_klass=cls,
            message=cls.build_message_content(obj=obj, **kwargs),
            attributes=cls.build_message_attributes(obj=obj, **kwargs),
            topic_name=cls.topic_name(obj=obj, **kwargs),
        )

    def run(
        self, message: dict, topic_name: str, attributes: dict[str, str] | None, headers: dict[str, str] | None = None
    ):
        message = self._build_message_with_headers(message=message, headers=headers)
        return self._get_publisher_client().publish(
            message=serialize(value=message),
            topic_id=topic_name,
            attributes=attributes,
        )

    @classmethod
    def set_up(cls) -> None: ...  # TODO: run over all models?

    @classmethod
    def topic_name(cls, obj: Model, **kwargs) -> str:
        name = cls.extract_model_name(obj=obj)
        if app_name := get_config(name="app_name"):
            delimiter = get_config(name="delimiter")
            name = f"{app_name}{delimiter}{name}"
        return name

    @classmethod
    def extract_model_name(cls, obj: Model) -> str:
        app_name = str(obj.__class__._meta.app_label).lower()
        model_name = str(obj.__class__._meta.model_name).lower()
        return f"{app_name}-{model_name}"

    @classmethod
    def build_message_content(cls, obj: Model, **kwargs) -> dict:
        raise NotImplementedError()

    @classmethod
    def build_message_attributes(cls, obj: Model, **kwargs) -> dict[str, str]:
        raise NotImplementedError()

    @classmethod
    @lru_cache()
    def _get_publisher_client(cls) -> CloudPublisher:
        return CloudPublisher()
