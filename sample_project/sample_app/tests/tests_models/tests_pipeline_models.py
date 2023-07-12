from unittest.mock import call, patch

from django.test import TestCase
from django_cloud_tasks.tests import factories


class PipelineModelTest(TestCase):
    def test_start_pipeline(self):
        pipeline = factories.PipelineFactory()
        leaf_already_completed = factories.RoutineWithoutSignalFactory(status="completed")
        pipeline.routines.add(leaf_already_completed)

        leaf_already_reverted = factories.RoutineWithoutSignalFactory(status="reverted")
        pipeline.routines.add(leaf_already_reverted)

        with patch("django_cloud_tasks.tasks.RoutineExecutorTask.asap") as task:
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

        with patch("django_cloud_tasks.tasks.RoutineExecutorTask.asap") as task:
            with self.assertNumQueries(7):
                pipeline.start()
        calls = [call(routine_id=first_routine.pk), call(routine_id=another_first_routine.pk)]
        task.assert_has_calls(calls, any_order=True)

    def test_revert_pipeline(self):
        pipeline = factories.PipelineFactory()

        leaf_already_reverted = factories.RoutineWithoutSignalFactory(status="reverted")
        pipeline.routines.add(leaf_already_reverted)

        with patch("django_cloud_tasks.tasks.RoutineReverterTask.asap") as task:
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

        with patch("django_cloud_tasks.tasks.RoutineReverterTask.asap") as task:
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
