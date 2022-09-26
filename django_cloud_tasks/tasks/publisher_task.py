# pylint: disable=no-member
from gcp_pilot.pubsub import CloudPublisher

from django_cloud_tasks.serializers import serialize
from django_cloud_tasks.tasks.task import Task


class PublisherTask(Task):
    # perform asynchronous publish to PubSub, with overhead in:
    # - publishing the message as Task
    # - receiving it through the endpoint
    # - and the finally publishing to PubSub
    # might be useful to use the Cloud Task throttling
    publish_immediately: bool = True
    enable_message_ordering: bool = False

    def run(self, topic_name: str, message: dict, attributes: dict[str, str] | None = None):
        return self.__client.publish(
            message=serialize(message),
            topic_id=self._full_topic_name(name=topic_name),
            attributes=attributes,
        )

    def delay(self, topic_name: str, message: dict, ordering_key: str | None = None, attributes: dict[str, str] = None):
        self.enable_message_ordering = ordering_key is not None

        if not self.publish_immediately:
            task_kwargs = dict(
                topic_name=self._full_topic_name(name=topic_name),
                message=message,
                attributes=attributes,
            )
            return super()._send(task_kwargs=task_kwargs)
        return self.run(topic_name=topic_name, message=message, attributes=attributes)

    def initialize(self, topic_name):
        self.__client.create_topic(
            topic_id=self._full_topic_name(name=topic_name),
        )

    def _full_topic_name(self, name):
        if self._app_name:
            return f"{self._app_name}{self._delimiter}{name}"
        return name

    @property
    def __client(self):
        return CloudPublisher(enable_message_ordering=self.enable_message_ordering)
