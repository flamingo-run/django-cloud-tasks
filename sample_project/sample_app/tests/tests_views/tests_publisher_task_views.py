from unittest.mock import patch, ANY

from django.test import TransactionTestCase


class PublisherTaskTest(TransactionTestCase):
    def test_propagate_headerss(self):
        url = "/create-person"
        data = {"name": "Harry Potter"}
        headers = {
            "traceparent": "trace-this-potato",
            "another-random-header": "please-do-not-propagate-this",
        }
        django_headers = {f"HTTP_{key.upper()}": value for key, value in headers.items()}
        with patch("django_cloud_tasks.tasks.publisher_task.CloudPublisher") as publisher:
            self.client.post(path=url, data=data, content_type="application/json", **django_headers)

        expected_attributes = {
            "any-custom-attribute": "yay!",
            "HTTP_Traceparent": "trace-this-potato",
        }
        publisher_instance = publisher.return_value
        publisher_instance.publish.assert_called_once_with(message=ANY, topic_id=ANY, attributes=expected_attributes)
