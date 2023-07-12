from contextlib import ExitStack
from unittest.mock import patch

from django.test import TestCase

from django_cloud_tasks.tasks import RoutineReverterTask
from django_cloud_tasks.tests import factories
from django_cloud_tasks.tests.tests_base import EagerTasksMixin
from sample_app.tests.tests_base_tasks import patch_cache_lock


class RoutineReverterTaskTest(EagerTasksMixin, TestCase):
    _mock_lock = None

    def setUp(self):
        super().setUp()

        patched_settings = self.settings(EAGER_TASKS=True)
        patched_settings.enable()
        self.addCleanup(patched_settings.disable)

        stack = ExitStack()
        self.mock_lock = stack.enter_context(patch_cache_lock())

    def test_process_revert_and_update_routine_to_reverted(self):
        routine = factories.RoutineWithoutSignalFactory(
            status="reverting",
            task_name="SayHelloTask",
            output={"spell": "Obliviate"},
        )
        with patch("sample_app.tasks.SayHelloTask.revert") as revert:
            RoutineReverterTask.asap(routine_id=routine.pk)
            revert.assert_called_once_with(data=routine.output)
            routine.refresh_from_db()
            self.assertEqual(routine.status, "reverted")
