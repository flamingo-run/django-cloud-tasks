import abc

from cachetools.func import lru_cache
from django.apps import apps
from django.db.models import Model
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


class ModelPublisherTask(PublisherTask, abc.ABC):
    # Just a specialized Task that publishes a Django model to PubSub
    # Since it cannot accept any random parameters, all its signatures have fixed arguments
    @classmethod
    def sync(cls, obj: Model, **kwargs):
        message = cls.build_message_content(obj=obj, **kwargs)
        attributes = cls.build_message_attributes(obj=obj, **kwargs)
        topic_name = cls.topic_name(obj=obj, **kwargs)
        return cls().run(message=message, attributes=attributes, topic_name=topic_name)

    @classmethod
    def asap(cls, obj: Model, **kwargs):
        message = cls.build_message_content(obj=obj, **kwargs)
        attributes = cls.build_message_attributes(obj=obj, **kwargs)
        topic_name = cls.topic_name(obj=obj, **kwargs)
        task_kwargs = {
            "message": message,
            "attributes": attributes,
            "topic_name": topic_name,
        }
        return cls.push(task_kwargs=task_kwargs)

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
    def set_up(cls) -> None:
        ...  # TODO: run over all models?

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
