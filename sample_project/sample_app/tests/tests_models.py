from typing import List
from unittest.mock import call, patch

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from freezegun import freeze_time

from django_cloud_tasks import exceptions, models
from django_cloud_tasks.tests import factories


class RoutineModelTest(TestCase):
    @freeze_time("2020-01-01")
    def tests_fail(self):
        routine = factories.RoutineWithoutSignalFactory(status="running", output=None, ends_at=None)
        error = {"error": "something went wrong"}
        with self.assertNumQueries(1):
            routine.fail(output=error)
        routine.refresh_from_db()
        self.assertEqual("failed", routine.status)
        self.assertEqual(error, routine.output)
        self.assertEqual(timezone.now(), routine.ends_at)

    @freeze_time("2020-01-01")
    def tests_complete(self):
        routine = factories.RoutineWithoutSignalFactory(status="running", output=None, ends_at=None)
        output = {"id": 42}
        with self.assertNumQueries(2):
            routine.complete(output=output)
        routine.refresh_from_db()
        self.assertEqual("completed", routine.status)
        self.assertEqual(output, routine.output)
        self.assertEqual(timezone.now(), routine.ends_at)
        self.assertNumQueries(1)

    @freeze_time("2020-01-01")
    def tests_enqueue(self):
        routine = factories.RoutineFactory()
        with patch("django_cloud_tasks.tasks.PipelineRoutineTask.delay") as task:
            with self.assertNumQueries(3):
                routine.enqueue()
            routine.refresh_from_db()
            self.assertEqual("scheduled", routine.status)
            self.assertEqual(timezone.now(), routine.starts_at)
        task.assert_called_once_with(routine_id=routine.pk)

    def tests_revert_completed_routine(self):
        routine = factories.RoutineWithoutSignalFactory(status="completed", output="{'id': 42}")
        with patch("django_cloud_tasks.tasks.PipelineRoutineRevertTask.delay") as revert_task:
            with self.assertNumQueries(3):
                routine.revert()
            routine.refresh_from_db()
            self.assertEqual("reverting", routine.status)
        revert_task.assert_called_once_with(routine_id=routine.pk)

    def tests_ensure_valid_task_name(self):
        task_name = "InvalidTaskName"
        with self.assertRaises(exceptions.TaskNotFound, msg=f"Task {task_name} not registered."):
            factories.RoutineFactory(task_name=task_name)

    def tests_enqueue_next_routines_after_completed(self):
        pipeline = factories.PipelineFactory()
        first_routine = factories.RoutineWithoutSignalFactory(status="running")
        pipeline.routines.add(first_routine)
        second_routine = factories.RoutineFactory()
        pipeline.routines.add(second_routine)
        third_routine = factories.RoutineFactory()
        pipeline.routines.add(third_routine)

        factories.RoutineVertexFactory(routine=first_routine, next_routine=second_routine)
        factories.RoutineVertexFactory(routine=first_routine, next_routine=third_routine)

        with patch("django_cloud_tasks.tasks.PipelineRoutineTask.delay") as task:
            with self.assertNumQueries(8):
                first_routine.status = "completed"
                first_routine.save()
        calls = [call(routine_id=second_routine.pk), call(routine_id=third_routine.pk)]
        task.assert_has_calls(calls, any_order=True)

    def tests_dont_enqueue_next_routines_after_completed_when_status_dont_change(self):
        pipeline = factories.PipelineFactory()
        first_routine = factories.RoutineWithoutSignalFactory(status="completed")
        pipeline.routines.add(first_routine)
        second_routine = factories.RoutineFactory()
        pipeline.routines.add(second_routine)
        third_routine = factories.RoutineFactory()
        pipeline.routines.add(third_routine)

        factories.RoutineVertexFactory(routine=first_routine, next_routine=second_routine)
        factories.RoutineVertexFactory(routine=first_routine, next_routine=third_routine)

        with patch("django_cloud_tasks.tasks.PipelineRoutineTask.delay") as task:
            with self.assertNumQueries(1):
                first_routine.status = "completed"
                first_routine.save()
        task.assert_not_called()

    def tests_enqueue_previously_routines_after_reverted(self):
        pipeline = factories.PipelineFactory()
        first_routine = factories.RoutineWithoutSignalFactory(status="completed")
        pipeline.routines.add(first_routine)
        second_routine = factories.RoutineFactory()
        pipeline.routines.add(second_routine)
        third_routine = factories.RoutineWithoutSignalFactory(status="reverting")
        pipeline.routines.add(third_routine)

        factories.RoutineVertexFactory(routine=first_routine, next_routine=second_routine)
        factories.RoutineVertexFactory(routine=first_routine, next_routine=third_routine)

        with patch("django_cloud_tasks.tasks.PipelineRoutineRevertTask.delay") as task:
            with self.assertNumQueries(5):
                third_routine.status = "reverted"
                third_routine.save()

        task.assert_called_once_with(routine_id=first_routine.pk)

    def tests_dont_enqueue_previously_routines_after_reverted_completed_when_status_dont_change(self):
        pipeline = factories.PipelineFactory()
        first_routine = factories.RoutineWithoutSignalFactory(status="completed")
        pipeline.routines.add(first_routine)
        second_routine = factories.RoutineFactory()
        pipeline.routines.add(second_routine)
        third_routine = factories.RoutineWithoutSignalFactory(status="reverted")
        pipeline.routines.add(third_routine)

        factories.RoutineVertexFactory(routine=first_routine, next_routine=second_routine)
        factories.RoutineVertexFactory(routine=first_routine, next_routine=third_routine)

        with patch("django_cloud_tasks.tasks.PipelineRoutineRevertTask.delay") as task:
            with self.assertNumQueries(1):
                third_routine.status = "reverted"
                third_routine.save()

        task.assert_not_called()

    def test_add_next(self):
        routine = factories.RoutineFactory()
        expected_routine_1 = {
            "task_name": "DummyRoutineTask",
            "body": {"spell": "onfundo"},
        }
        next_routine = routine.add_next(expected_routine_1)
        self.assertEqual(expected_routine_1["body"], next_routine.body)
        self.assertEqual(expected_routine_1["task_name"], next_routine.task_name)


class PipelineModelTest(TestCase):
    def tests_start_pipeline(self):
        pipeline = factories.PipelineFactory()
        leaf_already_completed = factories.RoutineWithoutSignalFactory(status="completed")
        pipeline.routines.add(leaf_already_completed)

        leaf_already_reverted = factories.RoutineWithoutSignalFactory(status="reverted")
        pipeline.routines.add(leaf_already_reverted)

        with patch("django_cloud_tasks.tasks.PipelineRoutineTask.delay") as task:
            with self.assertNumQueries(1):
                pipeline.start()
        task.assert_not_called()

        second_routine = factories.RoutineFactory()
        pipeline.routines.add(second_routine)
        third_routine = factories.RoutineFactory()
        pipeline.routines.add(third_routine)
        first_routine = factories.RoutineFactory()
        pipeline.routines.add(first_routine)

        another_first_routine = factories.RoutineFactory()
        pipeline.routines.add(another_first_routine)

        factories.RoutineVertexFactory(routine=second_routine, next_routine=third_routine)
        factories.RoutineVertexFactory(routine=first_routine, next_routine=second_routine)

        with patch("django_cloud_tasks.tasks.PipelineRoutineTask.delay") as task:
            with self.assertNumQueries(7):
                pipeline.start()
        calls = [call(routine_id=first_routine.pk), call(routine_id=another_first_routine.pk)]
        task.assert_has_calls(calls, any_order=True)

    def tests_revert_pipeline(self):
        pipeline = factories.PipelineFactory()

        leaf_already_reverted = factories.RoutineWithoutSignalFactory(status="reverted")
        pipeline.routines.add(leaf_already_reverted)

        with patch("django_cloud_tasks.tasks.PipelineRoutineRevertTask.delay") as task:
            with self.assertNumQueries(1):
                pipeline.revert()
        task.assert_not_called()

        second_routine = factories.RoutineFactory()
        pipeline.routines.add(second_routine)

        third_routine = factories.RoutineWithoutSignalFactory(status="completed")
        pipeline.routines.add(third_routine)

        first_routine = factories.RoutineFactory()
        pipeline.routines.add(first_routine)

        fourth_routine = factories.RoutineWithoutSignalFactory(status="completed")
        pipeline.routines.add(fourth_routine)

        factories.RoutineVertexFactory(routine=second_routine, next_routine=third_routine)
        factories.RoutineVertexFactory(routine=first_routine, next_routine=second_routine)

        with patch("django_cloud_tasks.tasks.PipelineRoutineRevertTask.delay") as task:
            with self.assertNumQueries(7):
                pipeline.revert()
        calls = [
            call(routine_id=fourth_routine.pk),
            call(routine_id=third_routine.pk),
        ]
        task.assert_has_calls(calls, any_order=True)

    def test_add_routine(self):
        pipeline = factories.PipelineFactory()
        expected_routine_1 = {
            "task_name": "DummyRoutineTask",
            "body": {"spell": "wingardium leviosa"},
        }
        routine = pipeline.add_routine(expected_routine_1)
        self.assertEqual(expected_routine_1["body"], routine.body)
        self.assertEqual(expected_routine_1["task_name"], routine.task_name)


class RoutineStateMachineTest(TestCase):
    def setUp(self):
        super().setUp()
        revert_routine_task = patch("django_cloud_tasks.tasks.PipelineRoutineRevertTask.delay")
        routine_task = patch("django_cloud_tasks.tasks.PipelineRoutineTask.delay")
        routine_task.start()
        revert_routine_task.start()
        self.addCleanup(routine_task.stop)
        self.addCleanup(revert_routine_task.stop)

    def _status_list(self, ignore_items: list) -> list:
        statuses = models.Routine.Statuses.values
        for item in ignore_items:
            statuses.remove(item)
        return statuses

    def test_dont_allow_initial_status_not_equal_pending(self):
        for status in self._status_list(ignore_items=["pending", "failed", "scheduled"]):
            msg_error = f"The initial routine's status must be 'pending' not '{status}'"
            with self.assertRaises(ValidationError, msg=msg_error):
                factories.RoutineFactory(status=status)

    def test_ignore_if_status_was_not_updated(self):
        routine = factories.RoutineFactory(status="pending")
        routine.status = "pending"
        routine.save()

    def test_allow_to_update_status_from_scheduled_to_running_or_failed(self):
        self.assert_machine_status(accepted_status=["running", "failed", "reverting"], from_status="scheduled")

    def test_allow_to_update_status_from_running_to_completed(self):
        self.assert_machine_status(
            accepted_status=["completed", "failed"],
            from_status="running",
        )

    def test_allow_to_update_status_from_completed_to_failed_or_reverting(self):
        self.assert_machine_status(accepted_status=["reverting"], from_status="completed")

    def test_allow_to_update_status_from_reverting_to_reverted(self):
        self.assert_machine_status(
            accepted_status=["reverted"],
            from_status="reverting",
        )

    def assert_machine_status(self, from_status: str, accepted_status: List[str]):
        for status in accepted_status:
            routine = factories.RoutineWithoutSignalFactory(status=from_status)
            routine.status = status
            routine.save()

        accepted_status.append(from_status)
        for status in self._status_list(ignore_items=accepted_status):
            msg_error = f"Status update from '{from_status}' to '{status}' is not allowed"
            with self.assertRaises(ValidationError, msg=msg_error):
                routine = factories.RoutineWithoutSignalFactory(status=from_status)
                routine.status = status
                routine.save()
