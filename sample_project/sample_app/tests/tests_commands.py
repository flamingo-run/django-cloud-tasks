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


class InitializeSubscribersTest(SimpleTestCase):
    def setUp(self):
        super().setUp()
        app_config = apps.get_app_config("django_cloud_tasks")
        app_name = patch.object(app_config, "app_name", new_callable=PropertyMock, return_value="potato")
        app_name.start()
        self.addCleanup(app_name.stop)
        self.app_config = app_config

    def _subscription(self, subscription_id: str, push_endpoint: str) -> Mock:
        subscription = Mock()
        subscription.name = f"projects/potato-project/subscriptions/{subscription_id}"
        subscription.push_config.push_endpoint = push_endpoint
        return subscription

    def _initialize(self, existing: List[Mock]) -> List[str]:
        with (
            patch_auth(),
            patch("gcp_pilot.pubsub.CloudSubscriber.list_subscriptions", return_value=existing),
            patch("gcp_pilot.pubsub.CloudSubscriber.create_or_update_subscription"),
            patch("gcp_pilot.pubsub.CloudSubscriber.delete_subscription") as delete,
        ):
            self.app_config.initialize_subscribers()
        return sorted(call.kwargs["subscription_id"] for call in delete.call_args_list)

    def test_deletes_every_subscription_of_a_removed_task(self):
        endpoint = "http://localhost:8080/subscriptions/GoneTask"
        existing = [
            self._subscription(subscription_id="gone-topic--potato", push_endpoint=endpoint),
            self._subscription(subscription_id="gone-topic--v2--potato", push_endpoint=endpoint),
        ]

        deleted = self._initialize(existing=existing)

        self.assertEqual(["gone-topic--potato", "gone-topic--v2--potato"], deleted)

    def test_deletes_a_stale_subscription_pushing_to_an_existing_task(self):
        from sample_app.tasks import PleaseNotifyMeTask

        endpoint = PleaseNotifyMeTask.subscription_url()
        existing = [
            self._subscription(subscription_id=PleaseNotifyMeTask.subscription_name(), push_endpoint=endpoint),
            self._subscription(subscription_id="old-potato-topic--potato", push_endpoint=endpoint),
        ]

        deleted = self._initialize(existing=existing)

        self.assertEqual(["old-potato-topic--potato"], deleted)

    def test_keeps_a_subscription_pushing_to_a_same_named_task_elsewhere(self):
        existing = [
            self._subscription(
                subscription_id="potato-topic--other-potato",
                push_endpoint="https://other.example.com/subscriptions/PleaseNotifyMeTask",
            ),
        ]

        deleted = self._initialize(existing=existing)

        self.assertEqual([], deleted)
