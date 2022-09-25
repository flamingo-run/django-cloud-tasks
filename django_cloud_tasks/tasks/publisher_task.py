# pylint: disable=no-member
from typing import Dict

from gcp_pilot.pubsub import CloudPublisher
from google.cloud import pubsub_v1

from django_cloud_tasks.serializers import serialize
from django_cloud_tasks.tasks.task import Task


class PublisherTask(Task):
    # perform asynchronous publish to PubSub, with overhead in:
    # - publishing the message as Task
    # - receiving it through the endpoint
    # - and the finally publishing to PubSub
    # might be useful to use the Cloud Task throttling
    publish_immediately = True

    _ordered_client = None
    _unordered_client = None

    def __init__(self, enable_message_ordering=False) -> None:
        super().__init__()
        self.enable_message_ordering = enable_message_ordering

    def run(self, topic_name: str, message: Dict, attributes: Dict[str, str] = None):
        return self.__client.publish(
            message=serialize(message),
            topic_id=self._full_topic_name(name=topic_name),
            attributes=attributes,
        )

    def delay(self, topic_name: str, message: Dict, attributes: Dict[str, str] = None):
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

    def __ordered_client(self):
        if not self.__class__._ordered_client:
            publisher_options = pubsub_v1.types.PublisherOptions(enable_message_ordering=True)
            self.__class__._ordered_client = CloudPublisher(publisher_options=publisher_options)
        return self.__class__._ordered_client

    def __unordered_client(self):
        if not self.__class__._unordered_client:
            publisher_options = pubsub_v1.types.PublisherOptions(enable_message_ordering=False)
            self.__class__._unordered_client = CloudPublisher(publisher_options=publisher_options)
        return self.__class__._unordered_client

    @property
    def __client(self):
        return self.__ordered_client() if self.enable_message_ordering else self.__unordered_client()
