from unittest.mock import patch, Mock

from django.test import SimpleTestCase

from sample_project.sample_app import tasks


class TasksTest(SimpleTestCase):
    def setUp(self):
        fake_config = Mock()
        config = patch('django_cloud_tasks.client.CloudTasksClient.config', return_value=fake_config)
        config.start()
        self.addCleanup(config.stop)

        fake_credentials = Mock()
        credentials = patch('django_cloud_tasks.client.CloudTasksClient.credentials', return_value=fake_credentials)
        credentials.start()
        self.addCleanup(credentials.stop)

    def patch_push(self, **kwargs):
        return patch('django_cloud_tasks.client.CloudTasksClient.push', **kwargs)

    def test_task_async(self):
        with self.patch_push() as push:
            tasks.CalculatePriceTask().delay(price=30, quantity=4, discount=0.2)

        expected_call = dict(
            name='CalculatePriceTask',
            queue='tasks',
            url='http://localhost:8080/tasks/CalculatePriceTask',
            payload={'price': 30, 'quantity': 4, 'discount': 0.2},
        )
        push.assert_called_once_with(**expected_call)

    def test_task_eager(self):
        with self.settings(EAGER_TASKS=True):
            r = tasks.CalculatePriceTask().delay(price=30, quantity=4, discount=0.2)
        self.assertGreater(r, 0)
