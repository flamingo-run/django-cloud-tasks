import json
from unittest.mock import patch

from django.apps import apps
from django.test import SimpleTestCase
from gcp_pilot.exceptions import DeletedRecently
from gcp_pilot.mocker import patch_auth

from django_cloud_tasks import exceptions
from django_cloud_tasks.tasks import PublisherTask
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

    def test_get_task(self):
        app_config = apps.get_app_config('django_cloud_tasks')

        self.assertEqual(PublisherTask, app_config.get_task(name="PublisherTask"))

    def test_get_task_not_found(self):
        app_config = apps.get_app_config('django_cloud_tasks')

        with self.assertRaises(exceptions.TaskNotFound):
            app_config.get_task(name="PotatoTask")

    def test_task_async(self):
        with self.patch_push() as push:
            with patch_auth():
                tasks.CalculatePriceTask().delay(price=30, quantity=4, discount=0.2)

        expected_call = dict(
            queue_name='tasks',
            url='http://localhost:8080/tasks/CalculatePriceTask',
            payload=json.dumps({'price': 30, 'quantity': 4, 'discount': 0.2}),
        )
        push.assert_called_once_with(**expected_call)

    def test_task_async_only_once(self):
        with self.patch_push() as push:
            with patch_auth():
                tasks.FailMiserablyTask().delay(magic_number=666)

        expected_call = dict(
            task_name='FailMiserablyTask',
            queue_name='tasks',
            url='http://localhost:8080/tasks/FailMiserablyTask',
            payload=json.dumps({'magic_number': 666}),
            unique=False,
        )
        push.assert_called_once_with(**expected_call)

    def test_task_async_reused_queue(self):
        effects = [DeletedRecently('Queue tasks'), None]
        with self.patch_push(side_effect=effects) as push:
            with patch_auth():
                tasks.CalculatePriceTask().delay(price=30, quantity=4, discount=0.2)

        expected_call = dict(
            queue_name='tasks',
            url='http://localhost:8080/tasks/CalculatePriceTask',
            payload=json.dumps({'price': 30, 'quantity': 4, 'discount': 0.2}),
        )
        expected_backup_call = expected_call
        expected_backup_call['queue_name'] += '--temp'

        self.assertEqual(2, push.call_count)
        push.assert_any_call(**expected_call)
        push.assert_called_with(**expected_backup_call)

    def test_task_eager(self):
        with self.settings(EAGER_TASKS=True):
            with patch_auth():
                response = tasks.CalculatePriceTask().delay(price=30, quantity=4, discount=0.2)
        self.assertGreater(response, 0)
