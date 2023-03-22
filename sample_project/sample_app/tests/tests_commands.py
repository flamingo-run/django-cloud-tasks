from io import StringIO
from typing import List
from unittest.mock import Mock, PropertyMock, patch

from django.apps import apps
from django.core.management import call_command
from django.test import SimpleTestCase
from gcp_pilot.mocker import patch_auth


class CommandsTest(SimpleTestCase):
    def patch_schedule(self):
        return patch("gcp_pilot.scheduler.CloudScheduler.put")

    def patch_subscribe(self):
        return patch("gcp_pilot.pubsub.CloudSubscriber.create_subscription")

    def patch_get_scheduled(self, names: List[str] = None):
        jobs = []
        for name in names or []:
            job = Mock()
            job.name = f"/app/jobs/{name}"
            jobs.append(job)
        return patch("gcp_pilot.scheduler.CloudScheduler.list", return_value=jobs)

    def patch_delete_schedule(self):
        return patch("gcp_pilot.scheduler.CloudScheduler.delete")

    def _assert_command(
        self,
        command: str,
        params: List[str] = None,
        expected_schedule_calls: int = 0,
        expected_subscribe_calls: int = 0,
        expected_output: str = None,
    ):
        out = StringIO()
        with patch_auth():
            with self.patch_schedule() as schedule:
                with self.patch_subscribe() as subscribe:
                    call_params = params or []
                    call_command(command, *call_params, no_color=True, stdout=out)
        self.assertEqual(expected_schedule_calls, schedule.call_count)
        self.assertEqual(expected_subscribe_calls, subscribe.call_count)
        if expected_output:
            self.assertEqual(expected_output, out.getvalue())

    def test_initialize_tasks(self):
        self._assert_command(
            command="initialize_tasks",
            expected_schedule_calls=1,
            expected_subscribe_calls=2,
        )

    def test_schedule_tasks(self):
        expected_output = "Successfully scheduled 1 tasks to domain http://localhost:8080\n- [+] SaySomethingTask\n"
        self._assert_command(
            command="schedule_tasks",
            expected_schedule_calls=1,
            expected_output=expected_output,
        )

    def test_schedule_tasks_with_obsolete(self):
        expected_output = (
            "Successfully scheduled 3 tasks to domain http://localhost:8080"
            "\n- [+] SaySomethingTask"
            "\n- [-] potato_task_1"
            "\n- [-] potato_task_2\n"
        )

        names = ["potato_task_1", "potato_task_2"]
        app_config = apps.get_app_config("django_cloud_tasks")
        with patch.object(app_config, "app_name", new_callable=PropertyMock, return_value="potato"):
            with self.patch_get_scheduled(names=names):
                with self.patch_delete_schedule() as delete:
                    self._assert_command(
                        command="schedule_tasks",
                        expected_schedule_calls=1,
                        expected_output=expected_output,
                    )
                self.assertEqual(2, delete.call_count)

    def test_initialize_subscribers(self):
        expected_output = (
            "Successfully initialized 2 subscribers to domain http://localhost:8080\n"
            "- [+] ParentSubscriberTask\n"
            "- [+] PleaseNotifyMeTask\n"
        )
        self._assert_command(
            command="initialize_subscribers",
            expected_subscribe_calls=2,
            expected_output=expected_output,
        )
