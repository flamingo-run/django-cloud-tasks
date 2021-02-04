import json
from unittest.mock import patch

from django.apps import apps
from django.test import SimpleTestCase
from gcp_pilot.mocker import patch_auth

from sample_project.sample_app import tasks


class TasksTest(SimpleTestCase):
    def patch_push(self, **kwargs):
        return patch('gcp_pilot.tasks.CloudTasks.push', **kwargs)

    def test_registered_tasks(self):
        app_config = apps.get_app_config('django_cloud_tasks')

        expected_tasks = {'PublisherTask', 'CalculatePriceTask', 'FailMiserablyTask', 'OneBigDedicatedTask'}
        self.assertEqual(expected_tasks, set(app_config.on_demand_tasks))

        expected_tasks = {'SaySomethingTask'}
        self.assertEqual(expected_tasks, set(app_config.periodic_tasks))

        expected_tasks = {'PleaseNotifyMeTask'}
        self.assertEqual(expected_tasks, set(app_config.subscriber_tasks))

    def test_task_async(self):
        with self.patch_push() as push:
            with patch_auth():
                tasks.CalculatePriceTask().delay(price=30, quantity=4, discount=0.2)

        expected_call = dict(
            task_name='CalculatePriceTask',
            queue_name='tasks',
            url='http://localhost:8080/tasks/CalculatePriceTask',
            payload=json.dumps({'price': 30, 'quantity': 4, 'discount': 0.2}),
        )
        push.assert_called_once_with(**expected_call)

    def test_task_eager(self):
        with self.settings(EAGER_TASKS=True):
            with patch_auth():
                r = tasks.CalculatePriceTask().delay(price=30, quantity=4, discount=0.2)
        self.assertGreater(r, 0)
