import abc

from cachetools.func import lru_cache
from gcp_pilot.pubsub import CloudPublisher

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

    def run(self, message: dict, attributes: dict[str, str] | None = None):
        return self._get_publisher_client().publish(
            message=serialize(value=message),
            topic_id=self.topic_name(),
            attributes=attributes,
        )

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
