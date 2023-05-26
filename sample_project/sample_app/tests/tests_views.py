from unittest.mock import patch, ANY

from django.test import SimpleTestCase, TransactionTestCase
from gcp_pilot.pubsub import Message
from gcp_pilot.mocker import patch_auth


class AuthenticationMixin(SimpleTestCase):
    def setUp(self) -> None:
        auth = patch_auth()
        auth.start()
        self.addCleanup(auth.stop)
        super().setUp()


class TaskViewTest(AuthenticationMixin):
    def url(self, name):
        return f"/tasks/{name}"

    def test_task_called(self):
        data = {
            "price": 300,
            "quantity": 4,
            "discount": 0.2,
        }
        url = self.url(name="CalculatePriceTask")
        response = self.client.post(path=url, data=data, content_type="application/json")
        self.assertEqual(200, response.status_code)
        self.assertEqual({"result": 960.0, "status": "executed"}, response.json())

    def test_task_called_with_internal_error(self):
        data = {
            "price": 300,
            "quantity": "wtf",
            "discount": 0.2,
        }
        url = self.url(name="CalculatePriceTask")
        with self.assertRaises(TypeError):
            self.client.post(path=url, data=data, content_type="application/json")

    def test_task_not_found(self):
        data = {}
        url = self.url(name="PotatoTask")
        response = self.client.post(path=url, data=data)
        self.assertEqual(404, response.status_code)

        expected_response = {
            "error": "Task PotatoTask not found",
        }
        self.assertEqual(expected_response, response.json())

    def test_task_called_with_get(self):
        url = self.url(name="CalculatePriceTask")
        response = self.client.get(path=url)
        self.assertEqual(405, response.status_code)

    def test_task_called_with_put(self):
        data = {}
        url = self.url(name="CalculatePriceTask")
        response = self.client.put(path=url, data=data)
        self.assertEqual(405, response.status_code)

    def test_task_called_with_delete(self):
        url = self.url(name="CalculatePriceTask")
        response = self.client.delete(path=url)
        self.assertEqual(405, response.status_code)

    def test_nested_task_called(self):
        data = {
            "name": "you",
        }
        url = self.url(name="OneBigDedicatedTask")
        response = self.client.post(path=url, data=data, content_type="application/json")
        self.assertEqual(200, response.status_code)
        self.assertEqual({"result": "Chuck Norris is better than you", "status": "executed"}, response.json())

    def test_propagate_headers(self):
        data = {
            "price": 10,
            "quantity": 42,
        }
        headers = {
            "traceparent": "trace-this-potato",
            "another-random-header": "please-do-not-propagate-this",
        }

        url = self.url(name="ParentCallingChildTask")
        django_headers = {f"HTTP_{key.upper()}": value for key, value in headers.items()}

        with patch("gcp_pilot.tasks.CloudTasks.push") as push:
            with patch("django_cloud_tasks.tasks.TaskMetadata.from_task_obj"):
                self.client.post(path=url, data=data, content_type="application/json", **django_headers)

        expected_kwargs = {
            "queue_name": "tasks",
            "url": "http://localhost:8080/tasks/CalculatePriceTask",
            "payload": '{"price": 10, "quantity": 42, "discount": 0}',
            "headers": {"Traceparent": "trace-this-potato", "X-CloudTasks-Projectname": ANY},
        }
        push.assert_called_once_with(**expected_kwargs)

    def test_absorb_headers(self):
        data = {}
        headers = {
            "traceparent": "trace-this-potato",
            "another-random-header": "please-do-not-propagate-this",
        }

        url = self.url(name="ExposeCustomHeadersTask")
        django_headers = {f"HTTP_{key.upper()}": value for key, value in headers.items()}

        response = self.client.post(path=url, data=data, content_type="application/json", **django_headers)

        expected_content = {"Traceparent": "trace-this-potato"}
        self.assertEqual(expected_content, response.json()["result"])


class SubscriberTaskViewTest(AuthenticationMixin):
    def url(self, name):
        return f"/subscriptions/{name}"

    def trigger_subscriber(self, content, attributes):
        url = "/subscriptions/ParentSubscriberTask"
        message = Message(
            id="i-dont-care",
            data=content,
            attributes=attributes,
            subscription="potato",
        )
        return self.client.post(path=url, data=message.dump(), content_type="application/json")

    def test_propagate_headers(self):
        content = {
            "price": 10,
            "quantity": 42,
        }
        attributes = {
            "HTTP_traceparent": "trace-this-potato",
            "HTTP_another-random-header": "please-do-not-propagate-this",
        }

        with patch("gcp_pilot.tasks.CloudTasks.push") as push:
            with patch("django_cloud_tasks.tasks.TaskMetadata.from_task_obj"):
                self.trigger_subscriber(content=content, attributes=attributes)

        expected_kwargs = {
            "queue_name": "tasks",
            "url": "http://localhost:8080/tasks/CalculatePriceTask",
            "payload": '{"price": 10, "quantity": 42}',
            "headers": {"Traceparent": "trace-this-potato", "X-CloudTasks-Projectname": ANY},
        }
        push.assert_called_once_with(**expected_kwargs)


class PublisherTaskTest(TransactionTestCase):
    def setUp(self) -> None:
        auth = patch_auth()
        auth.start()
        self.addCleanup(auth.stop)
        super().setUp()

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
