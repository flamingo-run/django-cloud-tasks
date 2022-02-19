from django_cloud_tasks.tests.factories import RoutineWithoutSignalFactory


class RoutineTaskTestMixin:
    def tests_revert_should_revert_routine(self):
        routine = RoutineWithoutSignalFactory(status="reverting", task_name=f"{self.task.name()}")
        self.task().revert(data=self.task_revert_data_params, _meta={"routine_id": routine.id})
        routine.refresh_from_db()
        self.assertEqual("reverted", routine.status)

    def tests_run_expects_return_dict(self):
        output = self.task().run(**self.task_run_params)
        self.assertIsInstance(output, dict)

    @property
    def task(self):
        raise NotImplementedError()

    @property
    def task_run_params(self):
        return {}

    @property
    def task_revert_data_params(self):
        return {}
