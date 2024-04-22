from unittest.mock import patch, ANY

from django.test import TransactionTestCase
from gcp_pilot.mocker import patch_auth

from sample_app import models
import json


class PublisherTaskTest(TransactionTestCase):
    def setUp(self):
        super().setUp()
        auth = patch_auth()
        auth.start()
        self.addCleanup(auth.stop)

    def test_propagate_headers(self):
        url = "/create-person"
        data = {"name": "Harry Potter"}
        headers = {
            "traceparent": "trace-this-potato",
            "another-random-header": "please-do-not-propagate-this",
        }
        django_headers = {f"HTTP_{key.upper()}": value for key, value in headers.items()}
        with patch("django_cloud_tasks.tasks.publisher_task.CloudPublisher.publish") as publish:
            result = self.client.post(path=url, data=data, content_type="application/json", **django_headers)

        self.assertEqual(201, result.status_code)
        expected_message = json.dumps(
            {"id": result.json()["pk"], "name": "Harry Potter", "_http_headers": {"Traceparent": "trace-this-potato"}}
        )
        expected_attributes = {"any-custom-attribute": "yay!", "event": "saved"}
        publish.assert_called_once_with(message=expected_message, topic_id=ANY, attributes=expected_attributes)

    def test_usage_inside_transaction__success(self):
        with patch("django_cloud_tasks.tasks.publisher_task.CloudPublisher.publish"):
            existing = models.Person.objects.create(name="Potter Harry")

        url = "/replace-person"
        data = {"name": "Harry Potter", "person_to_replace_id": existing.pk}
        with patch("django_cloud_tasks.tasks.publisher_task.CloudPublisher.publish") as publish:
            result = self.client.post(path=url, data=data, content_type="application/json")

        self.assertEqual(201, result.status_code)
        self.assertEqual(2, publish.call_count)

        expected_message = json.dumps({"id": existing.pk, "name": "Potter Harry"})
        expected_attributes = {"any-custom-attribute": "yay!", "event": "deleted"}
        publish.assert_any_call(message=expected_message, topic_id=ANY, attributes=expected_attributes)

        expected_message = json.dumps({"id": result.json()["pk"], "name": "Harry Potter"})
        expected_attributes = {"any-custom-attribute": "yay!", "event": "saved"}
        publish.assert_any_call(message=expected_message, topic_id=ANY, attributes=expected_attributes)

    def test_usage_inside_transaction__rollback(self):
        url = "/replace-person"
        unexisting_pk = "1234"
        data = {"name": "Harry Potter", "person_to_replace_id": unexisting_pk}
        with patch("django_cloud_tasks.tasks.publisher_task.CloudPublisher.publish") as publish:
            result = self.client.post(path=url, data=data, content_type="application/json")
            self.assertEqual(404, result.status_code)

        self.assertEqual(0, publish.call_count)
