from typing import List
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase
from django_cloud_tasks import models
from django_cloud_tasks.tests import factories


class RoutineStateMachineTest(TestCase):
    def setUp(self):
        super().setUp()
        revert_routine_task = patch("django_cloud_tasks.tasks.RoutineReverterTask.asap")
        routine_task = patch("django_cloud_tasks.tasks.RoutineExecutorTask.asap")
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
