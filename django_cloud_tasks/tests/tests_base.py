from unittest.mock import patch


def eager_tasks():
    return patch("django_cloud_tasks.tasks.Task.eager", return_value=True)


class EagerTasksMixin:
    def setUp(self):
        super().setUp()

        mock_eager = eager_tasks()
        mock_eager.start()
        self.addCleanup(mock_eager.stop)


class RoutineTaskTestMixin(EagerTasksMixin):
    def test_revert_should_revert_routine(self):
        # When not implemented this method raises an Error
        self.task.revert(data=self.task_revert_data_params)

    def test_run_expects_return_dict(self):
        output = self.task.sync(**self.task_run_params)
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
