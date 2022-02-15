# pylint: disable=no-member
from typing import Dict

from google.cloud import pubsub_v1
from gcp_pilot.pubsub import CloudPublisher

from django_cloud_tasks.helpers import run_coroutine
from django_cloud_tasks.serializers import serialize
from django_cloud_tasks import tasks


class PublisherTask(tasks.Task):
    # perform asynchronous publish to PubSub, with overhead in:
    # - publishing the message as Task
    # - receiving it through the endpoint
    # - and the finally publishing to PubSub
    # might be useful to use the Cloud Task throttling
    publish_immediately = True

    def __init__(self, enable_message_ordering=False) -> None:
        super().__init__()
        self.enable_message_ordering = enable_message_ordering

    def run(self, topic_name: str, message: Dict, attributes: Dict[str, str] = None):
        return run_coroutine(
            handler=self.__client.publish,
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
        run_coroutine(
            handler=self.__client.create_topic,
            topic_id=self._full_topic_name(name=topic_name),
        )

    def _full_topic_name(self, name):
        if self._app_name:
            return f"{self._app_name}{self._delimiter}{name}"
        return name

    @property
    def __client(self):
        publisher_options = pubsub_v1.types.PublisherOptions(
            enable_message_ordering=self.enable_message_ordering,
        )

        return CloudPublisher(publisher_options=publisher_options)
