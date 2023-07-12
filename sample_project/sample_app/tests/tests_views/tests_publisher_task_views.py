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

        with patch("gcp_pilot.pubsub.CloudPublisher.publish") as publish:
            self.client.post(path=url, data=data, content_type="application/json", **django_headers)

        expected_attributes = {"HTTP_Traceparent": "trace-this-potato", "any-custom-attribute": "yay!"}
        publish.assert_called_once_with(message=ANY, topic_id=ANY, attributes=expected_attributes)
