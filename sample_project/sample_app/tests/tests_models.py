from typing import List
from unittest.mock import patch, call
from datetime import datetime
from freezegun import freeze_time
from django.test import TestCase
from django.core.exceptions import ValidationError
from django_cloud_tasks import models, exceptions
from django_cloud_tasks.tests import factories


class RoutineModelTest(TestCase):
    @freeze_time("2020-01-01")
    def tests_fail(self):
        routine = factories.RoutineWithoutSignalFactory(status="running", output=None, ends_at=None)
        error = {"error": "something went wrong"}
        routine.fail(output=error)
        routine.refresh_from_db()
        self.assertEqual("failed", routine.status)
        self.assertEqual(error, routine.output)
        self.assertEqual(datetime.now(), routine.ends_at.replace(tzinfo=None))

    @freeze_time("2020-01-01")
    def tests_complete(self):
        routine = factories.RoutineWithoutSignalFactory(status="running", output=None, ends_at=None)
        output = {"id": 42}
        routine.complete(output=output)
        routine.refresh_from_db()
        self.assertEqual("completed", routine.status)
        self.assertEqual(output, routine.output)
        self.assertEqual(datetime.now(), routine.ends_at.replace(tzinfo=None))

    @freeze_time("2020-01-01")
    def tests_enqueue(self):
        routine = factories.RoutineFactory()
        with patch("django_cloud_tasks.tasks.PipelineRoutineTask.delay") as task:
            routine.enqueue()
            routine.refresh_from_db()
            self.assertEqual("scheduled", routine.status)
            self.assertEqual(datetime.now(), routine.starts_at.replace(tzinfo=None))
        task.assert_called_once_with(routine_id=routine.pk)

    def tests_revert_completed_routine(self):
        routine = factories.RoutineWithoutSignalFactory(status="completed", output="{'id': 42}")
        with patch("django_cloud_tasks.tests.factories.DummyRoutineTask.revert") as revert_task:
            routine.revert()
            routine.refresh_from_db()
            self.assertEqual("reverting", routine.status)
        revert_task.assert_called_once_with(data=routine.output, _meta={"routine_id": routine.pk})

    def tests_revert_not_processed_routine(self):
        routine = factories.RoutineFactory()
        with patch("django_cloud_tasks.tests.factories.DummyRoutineTask.revert") as revert_task:
            routine.revert()
            routine.refresh_from_db()
            self.assertEqual("aborted", routine.status)
        revert_task.assert_not_called()

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

        with patch("django_cloud_tasks.tests.factories.DummyRoutineTask.revert") as task:
            third_routine.status = "reverted"
            third_routine.save()

        task.assert_called_once_with(data=first_routine.output, _meta={"routine_id": first_routine.pk})

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

        with patch("django_cloud_tasks.tests.factories.DummyRoutineTask.revert") as task:
            third_routine.status = "reverted"
            third_routine.save()

        task.assert_not_called()


class PipelineModelTest(TestCase):
    def tests_start_pipeline(self):
        pipeline = factories.PipelineFactory()
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
            pipeline.start()
        calls = [call(routine_id=first_routine.pk), call(routine_id=another_first_routine.pk)]
        task.assert_has_calls(calls, any_order=True)

    def tests_revert_pipeline(self):
        pipeline = factories.PipelineFactory()
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

        with patch("django_cloud_tasks.tests.factories.DummyRoutineTask.revert") as task:
            pipeline.revert()
        calls = [
            call(data=fourth_routine.output, _meta={"routine_id": fourth_routine.pk}),
            call(data=third_routine.output, _meta={"routine_id": third_routine.pk}),
        ]
        task.assert_has_calls(calls, any_order=True)


class RoutineStateMachineTest(TestCase):
    def setUp(self):
        super().setUp()
        routine_task = patch("django_cloud_tasks.tasks.PipelineRoutineTask.delay")
        routine_task.start()
        self.addCleanup(routine_task.stop)

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

    def test_allow_to_update_status_from_pending_or_failed_to_scheduled(self):
        self.assert_machine_status(accepted_status=["scheduled", "aborted"], from_status="pending")

    def test_allow_to_update_status_from_scheduled_to_running(self):
        self.assert_machine_status(accepted_status=["running"], from_status="scheduled")

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
