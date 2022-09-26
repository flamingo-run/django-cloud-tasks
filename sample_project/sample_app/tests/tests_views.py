from django.test import SimpleTestCase


class TaskViewTest(SimpleTestCase):
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
        self.assertEqual({"result": 960.0}, response.json())

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
            "available_tasks": [
                "PublisherTask",
                "RoutineLockTaskMixin",
                "PipelineRoutineRevertTask",
                "PipelineRoutineTask",
                "CalculatePriceTask",
                "FailMiserablyTask",
                "SayHelloTask",
                "SayHelloWithParamsTask",
                "BroadcastHelloTask",
                "OneBigDedicatedTask",
                "DummyRoutineTask",
                "SaySomethingTask",
            ],
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
        self.assertEqual({"result": "Chuck Norris is better than you"}, response.json())
