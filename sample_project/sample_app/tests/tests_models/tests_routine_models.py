from unittest.mock import call, patch

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from freezegun import freeze_time
from django.db import IntegrityError
from django_cloud_tasks.tests import factories


class RoutineModelTest(TestCase):
    @freeze_time("2020-01-01")
    def test_fail(self):
        routine = factories.RoutineWithoutSignalFactory(status="running", output=None, ends_at=None)
        error = {"error": "something went wrong"}
        with self.assertNumQueries(1):
            routine.fail(output=error)
        routine.refresh_from_db()
        self.assertEqual("failed", routine.status)
        self.assertEqual(error, routine.output)
        self.assertEqual(timezone.now(), routine.ends_at)

    @freeze_time("2020-01-01")
    def test_complete(self):
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
    def test_enqueue(self):
        routine = factories.RoutineFactory()
        with patch("django_cloud_tasks.tasks.RoutineExecutorTask.asap") as task:
            with self.assertNumQueries(3):
                routine.enqueue()
            routine.refresh_from_db()
            self.assertEqual("scheduled", routine.status)
            self.assertEqual(timezone.now(), routine.starts_at)
        task.assert_called_once_with(routine_id=routine.pk)

    def test_revert_completed_routine(self):
        routine = factories.RoutineWithoutSignalFactory(status="completed", output="{'id': 42}")
        with patch("django_cloud_tasks.tasks.RoutineReverterTask.asap") as revert_task:
            with self.assertNumQueries(3):
                routine.revert()
            routine.refresh_from_db()
            self.assertEqual("reverting", routine.status)
        revert_task.assert_called_once_with(routine_id=routine.pk)

    def test_ensure_valid_task_name(self):
        task_name = "InvalidTaskName"
        with self.assertRaises(ValidationError, msg=f"Task {task_name} not registered."):
            x = factories.RoutineFactory(task_name=task_name)
            print(x)

    def test_enqueue_next_routines_after_completed(self):
        pipeline = factories.PipelineFactory()
        first_routine = factories.RoutineWithoutSignalFactory(status="running")
        pipeline.routines.add(first_routine)
        second_routine = factories.RoutineFactory()
        pipeline.routines.add(second_routine)
        third_routine = factories.RoutineFactory()
        pipeline.routines.add(third_routine)

        factories.RoutineVertexFactory(routine=first_routine, next_routine=second_routine)
        factories.RoutineVertexFactory(routine=first_routine, next_routine=third_routine)

        with patch("django_cloud_tasks.tasks.RoutineExecutorTask.asap") as task:
            with self.assertNumQueries(8):
                first_routine.status = "completed"
                first_routine.save()
        calls = [call(routine_id=second_routine.pk), call(routine_id=third_routine.pk)]
        task.assert_has_calls(calls, any_order=True)

    def test_dont_enqueue_next_routines_after_completed_when_status_dont_change(self):
        pipeline = factories.PipelineFactory()
        first_routine = factories.RoutineWithoutSignalFactory(status="completed")
        pipeline.routines.add(first_routine)
        second_routine = factories.RoutineFactory()
        pipeline.routines.add(second_routine)
        third_routine = factories.RoutineFactory()
        pipeline.routines.add(third_routine)

        factories.RoutineVertexFactory(routine=first_routine, next_routine=second_routine)
        factories.RoutineVertexFactory(routine=first_routine, next_routine=third_routine)

        with patch("django_cloud_tasks.tasks.RoutineExecutorTask.asap") as task:
            with self.assertNumQueries(1):
                first_routine.status = "completed"
                first_routine.save()
        task.assert_not_called()

    def test_enqueue_previously_routines_after_reverted(self):
        pipeline = factories.PipelineFactory()
        first_routine = factories.RoutineWithoutSignalFactory(status="completed")
        pipeline.routines.add(first_routine)
        second_routine = factories.RoutineFactory()
        pipeline.routines.add(second_routine)
        third_routine = factories.RoutineWithoutSignalFactory(status="reverting")
        pipeline.routines.add(third_routine)

        factories.RoutineVertexFactory(routine=first_routine, next_routine=second_routine)
        factories.RoutineVertexFactory(routine=first_routine, next_routine=third_routine)

        with patch("django_cloud_tasks.tasks.RoutineReverterTask.asap") as task:
            with self.assertNumQueries(5):
                third_routine.status = "reverted"
                third_routine.save()

        task.assert_called_once_with(routine_id=first_routine.pk)

    def test_dont_enqueue_previously_routines_after_reverted_completed_when_status_dont_change(self):
        pipeline = factories.PipelineFactory()
        first_routine = factories.RoutineWithoutSignalFactory(status="completed")
        pipeline.routines.add(first_routine)
        second_routine = factories.RoutineFactory()
        pipeline.routines.add(second_routine)
        third_routine = factories.RoutineWithoutSignalFactory(status="reverted")
        pipeline.routines.add(third_routine)

        factories.RoutineVertexFactory(routine=first_routine, next_routine=second_routine)
        factories.RoutineVertexFactory(routine=first_routine, next_routine=third_routine)

        with patch("django_cloud_tasks.tasks.RoutineReverterTask.asap") as task:
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

    def test_ensure_max_retries_greater_than_attempt_count(self):
        with self.assertRaisesRegex(
            expected_exception=IntegrityError, expected_regex="constraint failed: max_retries_less_than_attempt_count"
        ):
            factories.RoutineFactory(max_retries=1, attempt_count=5)
