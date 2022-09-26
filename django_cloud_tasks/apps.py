import os
from typing import Iterable, Tuple

from django.apps import AppConfig
from django.conf import settings
from gcp_pilot.pubsub import CloudSubscriber
from gcp_pilot.scheduler import CloudScheduler

from django_cloud_tasks import exceptions


class DjangoCloudTasksAppConfig(AppConfig):
    default_auto_field = "django.db.models.AutoField"
    name = "django_cloud_tasks"
    verbose_name = "Django Cloud Tasks"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.on_demand_tasks = {}
        self.periodic_tasks = {}
        self.subscriber_tasks = {}
        self.domain = self._fetch_config(name="GOOGLE_CLOUD_TASKS_ENDPOINT", default="http://localhost:8080")
        self.app_name = self._fetch_config(name="GOOGLE_CLOUD_TASKS_APP_NAME", default=os.environ.get("APP_NAME", None))
        self.delimiter = self._fetch_config(name="GOOGLE_CLOUD_TASKS_DELIMITER", default="--")

    def get_task(self, name: str):
        if name in self.on_demand_tasks:
            return self.on_demand_tasks[name]
        if name in self.periodic_tasks:
            return self.periodic_tasks[name]
        if name in self.subscriber_tasks:
            return self.subscriber_tasks[name]
        raise exceptions.TaskNotFound(name=name)

    def get_backup_queue_name(self, original_name: str) -> str:
        return self._fetch_config(
            name="GOOGLE_CLOUD_TASKS_BACKUP_QUEUE_NAME",
            default=f"{original_name}{self.delimiter}temp",
        )

    def _fetch_config(self, name, default):
        return getattr(settings, name, os.environ.get(name, default))

    def register_task(self, task_class):
        from django_cloud_tasks.tasks.periodic_task import PeriodicTask  # pylint: disable=import-outside-toplevel
        from django_cloud_tasks.tasks.subscriber_task import SubscriberTask  # pylint: disable=import-outside-toplevel
        from django_cloud_tasks.tasks.task import Task  # pylint: disable=import-outside-toplevel

        containers = {
            SubscriberTask: self.subscriber_tasks,
            PeriodicTask: self.periodic_tasks,
            Task: self.on_demand_tasks,
        }
        for parent_klass, container in containers.items():
            if issubclass(task_class, parent_klass) and not getattr(task_class, "abstract", False):
                container[task_class.name()] = task_class
                break

    def schedule_tasks(self) -> Tuple[Iterable[str], Iterable[str], Iterable[str]]:
        client = CloudScheduler()

        def _get_tasks():
            names = []
            if not self.app_name:
                return names
            for job in client.list(prefix=self.app_name):
                schedule_name = job.name.split("/jobs/")[-1]
                names.append((schedule_name.split("--", 1)[-1], schedule_name))
            return names

        expected = self.periodic_tasks.copy()
        existing = dict(_get_tasks())

        to_add = set(expected) - set(existing)
        to_remove = set(existing) - set(expected)
        updated = set(expected) - set(to_add)

        for task_to_add in to_add:
            task_klass = expected[task_to_add]
            task_klass().schedule()

        for task_to_remove in to_remove:
            client.delete(name=existing[task_to_remove])

        return to_add, updated, to_remove

    def set_up_permissions(self):
        sub = CloudSubscriber()
        sub.set_up_permissions(email=sub.credentials.service_account_email)

    def initialize_subscribers(self) -> Tuple[Iterable[str], Iterable[str], Iterable[str]]:
        client = CloudSubscriber()

        def _get_subscriptions():
            names = []
            if not self.app_name:
                return names

            for subscription in client.list_subscriptions(suffix=self.app_name):
                subscription_id = subscription.name.rsplit("subscriptions/", 1)[-1]
                task_name = subscription.push_config.push_endpoint.rsplit("/", 1)[-1]
                names.append((task_name, subscription_id))
            return names

        expected = self.subscriber_tasks.copy()
        existing = dict(_get_subscriptions())

        to_add = set(expected) - set(existing)
        to_remove = set(existing) - set(expected)
        to_update = set(expected) - set(to_add)

        for task_to_add in to_add:
            task_klass = expected[task_to_add]
            task_klass().register()

        for task_to_remove in to_remove:
            client.delete_subscription(subscription_id=existing[task_to_remove])

        for task_to_update in to_update:
            task_klass = expected[task_to_update]
            task_klass().register()

        return to_add, to_update, to_remove

    def ready(self):
        from django_cloud_tasks import signals  # pylint: disable=import-outside-toplevel, unused-import
