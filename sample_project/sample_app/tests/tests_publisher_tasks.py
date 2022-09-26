import json
from unittest.mock import patch

from django.test import TestCase
from gcp_pilot.mocker import patch_auth

from sample_project.sample_app import tasks


class PublisherTaskTest(TestCase):
    def patch_push(self, **kwargs):
        return patch("gcp_pilot.tasks.CloudTasks.push", **kwargs)

    def patch_create_topic(self, **kwargs):
        return patch("gcp_pilot.pubsub.CloudPublisher.create_topic", **kwargs)

    def patch_publish(self, **kwargs):
        return patch("gcp_pilot.pubsub.CloudPublisher.publish", **kwargs)

    def test_initialize(self):
        with self.patch_create_topic() as create_topic:
            with patch_auth():
                tasks.BroadcastHelloTask().initialize(topic_name="broadcast")

        expected_call = dict(topic_id="broadcast")
        create_topic.assert_called_once_with(**expected_call)

    def test_task_publish_later(self):
        with self.patch_push() as push:
            with patch_auth():
                tasks.BroadcastHelloTask(publish_immediately=False).delay()

        expected_call = dict(
            queue_name="tasks",
            url="http://localhost:8080/tasks/BroadcastHelloTask",
            payload=json.dumps({"topic_name": "broadcast", "message": {"message": "hello"}, "attributes": None}),
        )
        push.assert_called_once_with(**expected_call)

    def test_task_delay(self):
        with self.patch_publish() as publish:
            with patch_auth():
                tasks.BroadcastHelloTask().delay()

        expected_call = dict(
            topic_id="broadcast",
            message=json.dumps({"message": "hello"}),
            attributes=None,
        )
        publish.assert_called_once_with(**expected_call)

    def test_task_ordered_delay(self):
        with self.patch_publish() as publish:
            with patch_auth():
                tasks.BroadcastHelloTask(enable_message_ordering=True).delay()

        expected_call = dict(
            topic_id="broadcast",
            message=json.dumps({"message": "hello"}),
            attributes=None,
        )
        publish.assert_called_once_with(**expected_call)
