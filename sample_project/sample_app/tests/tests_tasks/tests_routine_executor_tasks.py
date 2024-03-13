from datetime import datetime, UTC
from unittest.mock import patch

from django.test import TestCase

from django_cloud_tasks.tasks import RoutineExecutorTask, TaskMetadata
from django_cloud_tasks.tests import factories, tests_base
from django_cloud_tasks.tests.tests_base import EagerTasksMixin
from sample_app import tasks
from sample_app.tests.tests_base_tasks import patch_cache_lock


class RoutineExecutorTaskTest(EagerTasksMixin, TestCase):
    _mock_lock = None

    def setUp(self):
        super().setUp()

        self.mock_lock = patch_cache_lock()
        self.mock_lock.start()
        self.addCleanup(self.mock_lock.stop)

    def assert_routine_lock(self, routine_id: int, task_name: str = "RoutineExecutorTask"):
        self.mock_lock.assert_called_with(
            key=f"lock-{task_name}-{routine_id}",
            timeout=60,
            blocking_timeout=5,
        )

    def test_dont_process_completed_routine(self):
        routine = factories.RoutineWithoutSignalFactory(
            status="completed",
            task_name="SayHelloTask",
        )
        with self.assertLogs(level="INFO") as context:
            RoutineExecutorTask.asap(routine_id=routine.pk)
            self.assert_routine_lock(routine_id=routine.pk)
            self.assertEqual(context.output, [f"INFO:root:Routine #{routine.pk} is already completed"])

    def test_start_pipeline_revert_flow_if_exceeded_retries(self):
        routine = factories.RoutineWithoutSignalFactory(
            status="running",
            task_name="SayHelloTask",
            max_retries=3,
            attempt_count=1,
        )
        with (
            self.assertLogs(level="INFO") as context,
            patch("sample_app.tasks.SayHelloTask.sync", side_effect=Exception("any error")),
        ):
            RoutineExecutorTask.asap(routine_id=routine.pk)
            self.assertEqual(
                context.output,
                [
                    f"INFO:root:Routine #{routine.id} is running",
                    f"INFO:root:Routine #{routine.id} has failed",
                    f"INFO:root:Routine #{routine.id} is being enqueued to retry",
                    f"INFO:root:Routine #{routine.id} is running",
                    f"INFO:root:Routine #{routine.id} has failed",
                    f"INFO:root:Routine #{routine.id} is being enqueued to retry",
                    f"INFO:root:Routine #{routine.id} has exhausted retries and is being reverted",
                ],
            )

            self.assert_routine_lock(routine_id=routine.pk, task_name="RoutineReverterTask")

    def test_store_task_output_into_routine(self):
        routine = factories.RoutineWithoutSignalFactory(
            status="running",
            task_name="SayHelloTask",
            body={"attributes": [1, 2, 3]},
            attempt_count=1,
        )
        with self.assertLogs(level="INFO") as context:
            RoutineExecutorTask.sync(routine_id=routine.pk)
            self.assert_routine_lock(routine_id=routine.pk)
            routine.refresh_from_db()
            self.assertEqual(
                context.output,
                [
                    f"INFO:root:Routine #{routine.id} is running",
                    f"INFO:root:Routine #{routine.id} just completed",
                ],
            )
            self.assertEqual("completed", routine.status)
            self.assertEqual(2, routine.attempt_count)

    def test_retry_and_complete_task_processing_once_failure(self):
        routine = factories.RoutineWithoutSignalFactory(
            status="scheduled",
            task_name="SayHelloTask",
            body={"attributes": [1, 2, 3]},
            attempt_count=0,
            max_retries=2,
        )
        with (
            self.assertLogs(level="INFO") as context,
            patch("sample_app.tasks.SayHelloTask.sync", side_effect=[Exception("any error"), "success"]),
        ):
            RoutineExecutorTask.sync(routine_id=routine.pk)
            self.assert_routine_lock(routine_id=routine.pk)
            routine.refresh_from_db()
            self.assertEqual(
                context.output,
                [
                    f"INFO:root:Routine #{routine.id} is running",
                    f"INFO:root:Routine #{routine.id} has failed",
                    f"INFO:root:Routine #{routine.id} is being enqueued to retry",
                    f"INFO:root:Routine #{routine.id} is running",
                    f"INFO:root:Routine #{routine.id} just completed",
                ],
            )
            self.assertEqual("completed", routine.status)
            self.assertEqual(2, routine.attempt_count)


class SayHelloTaskTest(TestCase, tests_base.RoutineTaskTestMixin):
    @property
    def task(self):
        return tasks.SayHelloTask


class SayHelloWithParamsTaskTest(TestCase, tests_base.RoutineTaskTestMixin):
    @property
    def task(self):
        return tasks.SayHelloWithParamsTask

    @property
    def task_run_params(self):
        return {"spell": "Obliviate"}


class TestTaskMetadata(TestCase):
    some_date = datetime(1990, 7, 19, 15, 30, 42, tzinfo=UTC)

    @property
    def sample_headers(self) -> dict:
        return {
            "X-Cloudtasks-Taskexecutioncount": 7,
            "X-Cloudtasks-Taskretrycount": 1,
            "X-Cloudtasks-Tasketa": str(self.some_date.timestamp()),
            "X-Cloudtasks-Projectname": "wizard-project",
            "X-Cloudtasks-Queuename": "wizard-queue",
            "X-Cloudtasks-Taskname": "hp-1234567",
        }

    @property
    def sample_metadata(self) -> TaskMetadata:
        return TaskMetadata(
            project_id="wizard-project",
            queue_name="wizard-queue",
            task_id="hp-1234567",
            execution_number=7,
            dispatch_number=1,
            eta=self.some_date,
            is_cloud_scheduler=False,
        )

    @property
    def sample_cloud_scheduler_metadata(self) -> TaskMetadata:
        return TaskMetadata(
            project_id="wizard-project",
            queue_name="wizard-queue",
            task_id="hp-1234567",
            execution_number=7,
            dispatch_number=1,
            eta=self.some_date,
            is_cloud_scheduler=True,
            cloud_scheduler_job_name="wizard-api--LevitationTask",
            cloud_scheduler_schedule_time=datetime(2023, 11, 3, 15, 27, 0, tzinfo=UTC),
        )

    def test_create_from_headers(self):
        metadata = TaskMetadata.from_headers(headers=self.sample_headers)

        self.assertEqual(7, metadata.execution_number)
        self.assertEqual(1, metadata.dispatch_number)
        self.assertEqual(2, metadata.attempt_number)
        self.assertEqual(self.some_date, metadata.eta)
        self.assertEqual("wizard-project", metadata.project_id)
        self.assertEqual("wizard-queue", metadata.queue_name)
        self.assertEqual("hp-1234567", metadata.task_id)
        self.assertFalse(metadata.is_cloud_scheduler)
        self.assertIsNone(metadata.cloud_scheduler_job_name)
        self.assertIsNone(metadata.cloud_scheduler_schedule_time)

    def test_create_from_cloud_schedule_headers(self):
        metadata = TaskMetadata.from_headers(
            headers=self.sample_headers
            | {
                "X-Cloudscheduler": "true",
                "X-Cloudscheduler-Scheduletime": "2023-11-03T08:27:00-07:00",
                "X-Cloudscheduler-Jobname": "wizard-api--LevitationTask",
            }
        )

        self.assertTrue(metadata.is_cloud_scheduler)
        self.assertEqual("wizard-api--LevitationTask", metadata.cloud_scheduler_job_name)
        self.assertEqual(datetime(2023, 11, 3, 15, 27, 0, tzinfo=UTC), metadata.cloud_scheduler_schedule_time)

    def test_build_headers(self):
        headers = self.sample_metadata.to_headers()

        self.assertEqual("7", headers["X-Cloudtasks-Taskexecutioncount"])
        self.assertEqual("1", headers["X-Cloudtasks-Taskretrycount"])
        self.assertEqual(str(int(self.some_date.timestamp())), headers["X-Cloudtasks-Tasketa"])
        self.assertEqual("wizard-project", headers["X-Cloudtasks-Projectname"])
        self.assertEqual("wizard-queue", headers["X-Cloudtasks-Queuename"])
        self.assertEqual("hp-1234567", headers["X-Cloudtasks-Taskname"])
        self.assertNotIn("X-Cloudscheduler", headers)
        self.assertNotIn("X-Cloudscheduler-Scheduletime", headers)
        self.assertNotIn("X-Cloudscheduler-Jobname", headers)

    def test_build_cloud_scheduler_headers(self):
        headers = self.sample_cloud_scheduler_metadata.to_headers()

        self.assertEqual("7", headers["X-Cloudtasks-Taskexecutioncount"])
        self.assertEqual("1", headers["X-Cloudtasks-Taskretrycount"])
        self.assertEqual(str(int(self.some_date.timestamp())), headers["X-Cloudtasks-Tasketa"])
        self.assertEqual("wizard-project", headers["X-Cloudtasks-Projectname"])
        self.assertEqual("wizard-queue", headers["X-Cloudtasks-Queuename"])
        self.assertEqual("hp-1234567", headers["X-Cloudtasks-Taskname"])
        self.assertEqual("true", headers["X-Cloudscheduler"])
        self.assertEqual("2023-11-03T15:27:00+00:00", headers["X-Cloudscheduler-Scheduletime"])
        self.assertEqual("wizard-api--LevitationTask", headers["X-Cloudscheduler-Jobname"])

    def test_comparable(self):
        reference = self.sample_metadata

        metadata_a = TaskMetadata.from_headers(self.sample_headers)
        self.assertEqual(reference, metadata_a)

        metadata_b = TaskMetadata.from_headers(self.sample_headers)
        metadata_b.execution_number += 1
        self.assertNotEqual(reference, metadata_b)

        not_metadata = True
        self.assertNotEqual(reference, not_metadata)
