class RoutineTaskTestMixin:
    def tests_revert_should_revert_routine(self):
        # When not implemented this method raises an Error
        self.task().revert(data=self.task_revert_data_params)

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
