from unittest.mock import patch, ANY

from gcp_pilot.pubsub import Message
from sample_app.tests.tests_base_tasks import AuthenticationMixin


class SubscriberTaskViewTest(AuthenticationMixin):
    def url(self, name):
        return f"/subscriptions/{name}"

    @property
    def propagated_headers_key(self):
        return "_http_headers"

    def make_content(self, headers: dict):
        return {"price": 10, "quantity": 42, self.propagated_headers_key: headers}

    def trigger_subscriber(self, content):
        url = "/subscriptions/ParentSubscriberTask"
        message = Message(
            id="i-dont-care",
            data=content,
            attributes={},
            subscription="potato",
        )
        return self.client.post(path=url, data=message.dump(), content_type="application/json")

    def test_propagate_headers(self):
        headers = {
            "traceparent": "trace-this-potato",
        }
        content = self.make_content(headers=headers)

        with patch("gcp_pilot.tasks.CloudTasks.push") as push:
            with patch("django_cloud_tasks.tasks.TaskMetadata.from_task_obj"):
                self.trigger_subscriber(content=content)

        expected_kwargs = {
            "queue_name": "tasks",
            "url": "http://localhost:8080/tasks/CalculatePriceTask",
            "payload": '{"price": 10, "quantity": 42, "_http_headers": {"traceparent": "trace-this-potato"}}',
            "headers": {"Traceparent": "trace-this-potato", "X-CloudTasks-Projectname": ANY},
            "task_timeout": None,
        }
        push.assert_called_once_with(**expected_kwargs)

    def test_propagate_headers_as_uppercase(self):
        headers = {"X-Forwarded-Authorization": "user-token"}
        content = self.make_content(headers=headers)

        with patch("gcp_pilot.tasks.CloudTasks.push"), patch("django_cloud_tasks.tasks.TaskMetadata.from_task_obj"):
            response = self.trigger_subscriber(content=content)
        assert response.wsgi_request.META.get("HTTP_X_FORWARDED_AUTHORIZATION") == "user-token"
