from contextlib import ExitStack
import json
from unittest.mock import patch

from django.apps import apps
from django.test import SimpleTestCase, TestCase
from gcp_pilot.exceptions import DeletedRecently
from gcp_pilot.mocker import patch_auth
from django_cloud_tasks import exceptions, factories
from django_cloud_tasks.tasks import PublisherTask, PipelineRoutineTask
from sample_project.sample_app import tasks
from sample_project.sample_app.tests.tests_base_tasks import patch_cache_lock

class TasksTest(SimpleTestCase):
    def patch_push(self, **kwargs):
        return patch("gcp_pilot.tasks.CloudTasks.push", **kwargs)

    def test_registered_tasks(self):
        app_config = apps.get_app_config("django_cloud_tasks")

        expected_tasks = {"PublisherTask", "CalculatePriceTask", "FailMiserablyTask", "OneBigDedicatedTask", "PipelineRoutineTask", "SayHelloTask", "DummyRoutineTask"}
        self.assertEqual(expected_tasks, set(app_config.on_demand_tasks))

        expected_tasks = {"SaySomethingTask"}
        self.assertEqual(expected_tasks, set(app_config.periodic_tasks))

        expected_tasks = {"PleaseNotifyMeTask"}
        self.assertEqual(expected_tasks, set(app_config.subscriber_tasks))

    def test_get_task(self):
        app_config = apps.get_app_config("django_cloud_tasks")

        self.assertEqual(PublisherTask, app_config.get_task(name="PublisherTask"))

    def test_get_task_not_found(self):
        app_config = apps.get_app_config("django_cloud_tasks")

        with self.assertRaises(exceptions.TaskNotFound):
            app_config.get_task(name="PotatoTask")

    def test_task_async(self):
        with self.patch_push() as push:
            with patch_auth():
                tasks.CalculatePriceTask().delay(price=30, quantity=4, discount=0.2)

        expected_call = dict(
            queue_name="tasks",
            url="http://localhost:8080/tasks/CalculatePriceTask",
            payload=json.dumps({"price": 30, "quantity": 4, "discount": 0.2}),
        )
        push.assert_called_once_with(**expected_call)

    def test_task_async_only_once(self):
        with self.patch_push() as push:
            with patch_auth():
                tasks.FailMiserablyTask().delay(magic_number=666)

        expected_call = dict(
            task_name="FailMiserablyTask",
            queue_name="tasks",
            url="http://localhost:8080/tasks/FailMiserablyTask",
            payload=json.dumps({"magic_number": 666}),
            unique=False,
        )
        push.assert_called_once_with(**expected_call)

    def test_task_async_reused_queue(self):
        effects = [DeletedRecently("Queue tasks"), None]
        with self.patch_push(side_effect=effects) as push:
            with patch_auth():
                tasks.CalculatePriceTask().delay(price=30, quantity=4, discount=0.2)

        expected_call = dict(
            queue_name="tasks",
            url="http://localhost:8080/tasks/CalculatePriceTask",
            payload=json.dumps({"price": 30, "quantity": 4, "discount": 0.2}),
        )
        expected_backup_call = expected_call
        expected_backup_call["queue_name"] += "--temp"

        self.assertEqual(2, push.call_count)
        push.assert_any_call(**expected_call)
        push.assert_called_with(**expected_backup_call)

    def test_task_eager(self):
        with self.settings(EAGER_TASKS=True):
            with patch_auth():
                response = tasks.CalculatePriceTask().delay(price=30, quantity=4, discount=0.2)
        self.assertGreater(response, 0)


class PipelineRoutineTaskTest(TestCase):
    _mock_lock = None
    def setUp(self):
        super().setUp()

        patched_settings = self.settings(EAGER_TASKS=True)
        patched_settings.enable()
        self.addCleanup(patched_settings.disable)

        stack = ExitStack()
        self.mock_lock = stack.enter_context(patch_cache_lock())

    def assert_routine_lock(self, routine_id: int):
        self.mock_lock.assert_called_with(
            key=f"lock-PipelineRoutineTask-{routine_id}",
            timeout=60,
            blocking_timeout=5,
        )

    def tests_dont_process_completed_routine(self):
        routine = factories.RoutineWithoutSignalFactory(
            status="completed",
            task_name="SayHelloTask",
        )
        with self.assertLogs(level='INFO') as cm:
            PipelineRoutineTask().delay(routine_id=routine.pk)
            self.assert_routine_lock(routine_id=routine.pk)
            self.assertEqual(cm.output, [f"INFO:root:Routine #{routine.pk} is already completed"])

    def tests_start_pipeline_revert_flow_if_exceeded_retries(self):
        routine = factories.RoutineWithoutSignalFactory(
            status="running",
            task_name="SayHelloTask",
            max_retries=1,
            attempt_count=2,
        )
        with patch("django_cloud_tasks.models.Pipeline.revert") as revert:
            with self.assertLogs(level='INFO') as context:
                PipelineRoutineTask().delay(routine_id=routine.pk)
                self.assertEqual(context.output, [
                    f"INFO:root:Routine #{routine.id} has exhausted retries and is being reverted",
                ])
                self.assert_routine_lock(routine_id=routine.pk)
                revert.assert_called_once()

    def tests_store_task_output_into_routine(self):
        routine = factories.RoutineWithoutSignalFactory(
            status="running",
            task_name="SayHelloTask",
            body={"attributes": [1,2,3]},
            attempt_count=1,
        )
        with self.assertLogs(level='INFO') as cm:
            PipelineRoutineTask().run(routine_id=routine.pk)
            self.assert_routine_lock(routine_id=routine.pk)
            routine.refresh_from_db()
            self.assertEqual(cm.output, [
                f"INFO:root:Routine #{routine.id} is running",
                f"INFO:root:Routine #{routine.id} just completed",
            ])
            self.assertEqual("completed", routine.status)
            self.assertEqual(2, routine.attempt_count)

    def tests_fail_routine_if_task_has_failed(self):
        routine = factories.RoutineWithoutSignalFactory(
            status="running",
            task_name="SayHelloTask",
            body={"attributes": [1,2,3]},
            attempt_count=1,
        )
        with self.assertLogs(level='INFO') as cm:
            with patch("sample_project.sample_app.tasks.SayHelloTask.run", side_effect=Exception("any error")):
                with patch("django_cloud_tasks.models.Routine.enqueue") as enqueue:
                    PipelineRoutineTask().run(routine_id=routine.pk)
                    self.assert_routine_lock(routine_id=routine.pk)
                    routine.refresh_from_db()
                    self.assertEqual(cm.output, [
                        f"INFO:root:Routine #{routine.id} is running",
                        f"INFO:root:Routine #{routine.id} has failed",
                        f"INFO:root:Routine #{routine.id} has been enqueued for retry",
                    ])
                    self.assertEqual("failed", routine.status)
                    enqueue.assert_called_once()
                    self.assertEqual(2, routine.attempt_count)
