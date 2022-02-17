from unittest.mock import patch, call
from datetime import datetime
from freezegun import freeze_time
from django.test import TestCase
from django_cloud_tasks import factories


class RoutineModelTest(TestCase):
    @freeze_time("2020-01-01")
    def tests_fail(self):
        routine = factories.RoutineFactory(output=None, ends_at=None)
        error = {"error": "something went wrong"}
        routine.fail(output=error)
        routine.refresh_from_db()
        self.assertEqual("failed", routine.status)
        self.assertEqual(error, routine.output)
        self.assertEqual(datetime.now(), routine.ends_at.replace(tzinfo=None))

    @freeze_time("2020-01-01")
    def tests_complete(self):
        routine = factories.RoutineFactory(output=None, ends_at=None)
        output = {"id": 42}
        routine.complete(output=output)
        routine.refresh_from_db()
        self.assertEqual("completed", routine.status)
        self.assertEqual(output, routine.output)
        self.assertEqual(datetime.now(), routine.ends_at.replace(tzinfo=None))

    @freeze_time("2020-01-01")
    def tests_enqueue(self):
        routine = factories.RoutineFactory()
        with patch("django_cloud_tasks.tasks.RoutineTask.delay") as task:
            routine.enqueue()
            routine.refresh_from_db()
            self.assertEqual("scheduled", routine.status)
            self.assertEqual(datetime.now(), routine.starts_at.replace(tzinfo=None))
        task.assert_called_once_with(routine_id=routine.pk)

    def tests_revert_completed_routine(self):
        routine = factories.RoutineFactory(status="completed", output="{'id': 42}")
        with patch("django_cloud_tasks.factories.DummyRoutineTask.revert") as revert_task:
            routine.revert()
            routine.refresh_from_db()
            self.assertEqual("reverting", routine.status)
        revert_task.assert_called_once_with(data=routine.output, _meta={"routine_id": routine.pk})

    def tests_revert_not_processed_routine(self):
        routine = factories.RoutineFactory()
        with patch("django_cloud_tasks.factories.DummyRoutineTask.revert") as revert_task:
            routine.revert()
            routine.refresh_from_db()
            self.assertEqual("aborted", routine.status)
        revert_task.assert_not_called()

    def tests_ensure_valid_task_name(self):
        task_name = "InvalidTaskName"
        with self.assertRaises(ValidationError, msg=f"The task {task_name} was not found. Make sure {task_name} is properly set."):
            factories.RoutineFactory(task_name=task_name)

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

        with patch("django_cloud_tasks.tasks.RoutineTask.delay") as task:
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

        with patch("django_cloud_tasks.tasks.RoutineTask.revert") as task:
            pipeline.revert()
        calls = [
            call(data=fourth_routine.output, _meta={"routine_id": fourth_routine.pk}),
            call(data=third_routine.output, _meta={"routine_id": third_routine.pk})
        ]
        task.assert_has_calls(calls, any_order=True)
