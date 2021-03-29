import asyncio
import os
from typing import List, Tuple

from django.apps import AppConfig
from django.conf import settings
from gcp_pilot.pubsub import CloudSubscriber
from gcp_pilot.scheduler import CloudScheduler


class DjangoCloudTasksAppConfig(AppConfig):
    name = 'django_cloud_tasks'
    verbose_name = "Django Cloud Tasks"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.on_demand_tasks = {}
        self.periodic_tasks = {}
        self.subscriber_tasks = {}
        self.domain = self._fetch_config(name='GOOGLE_CLOUD_TASKS_ENDPOINT', default='http://localhost:8080')
        self.app_name = self._fetch_config(name='GOOGLE_CLOUD_TASKS_APP_NAME', default=os.environ.get('APP_NAME', None))
        self.delimiter = self._fetch_config(name='GOOGLE_CLOUD_TASKS_DELIMITER', default='--')

    def get_backup_queue_name(self, original_name: str) -> str:
        return self._fetch_config(
            name='GOOGLE_CLOUD_TASKS_BACKUP_QUEUE_NAME',
            default=f'{original_name}{self.delimiter}temp',
        )

    def _fetch_config(self, name, default):
        return getattr(settings, name, os.environ.get(name, default))

    def register_task(self, task_class):
        from django_cloud_tasks import tasks  # pylint: disable=import-outside-toplevel

        containers = {
            tasks.SubscriberTask: self.subscriber_tasks,
            tasks.PeriodicTask: self.periodic_tasks,
            tasks.Task: self.on_demand_tasks,
        }
        for parent_klass, container in containers.items():
            if issubclass(task_class, parent_klass) and not getattr(task_class, 'abstract', False):
                container[task_class.name()] = task_class
                break

    def schedule_tasks(self) -> Tuple[List[str], List[str]]:
        updated = []
        removed = []
        for _, task_klass in self.periodic_tasks.items():
            task = task_klass()
            task.schedule()
            updated.append(task.schedule_name)

        if self.app_name:
            client = CloudScheduler()
            for job in client.list(prefix=self.app_name):
                schedule_name = job.name.split('/jobs/')[-1]
                if schedule_name not in updated:
                    asyncio.run(client.delete(name=schedule_name))
                    removed.append(schedule_name)

        return updated, removed

    def set_up_permissions(self):
        sub = CloudSubscriber()
        routine = sub.set_up_permissions(email=sub.credentials.service_account_email)
        asyncio.run(routine)

    def initialize_subscribers(self) -> Tuple[List[str], List[str]]:
        updated = []
        removed = []

        for task_name, task_klass in self.subscriber_tasks.items():
            task_klass().register()
            updated.append(task_name)

        async def _get_subscriptions():
            names = []
            async for subscription in client.list_subscriptions(suffix=self.app_name):
                susbcription_name = subscription.name.rsplit('subscriptions/', 1)[-1]
                task_name = subscription.push_config.push_endpoint.rsplit('/', 1)[-1]
                names.append((susbcription_name, task_name))
            return names

        if self.app_name:
            client = CloudSubscriber()
            for (subscription_id, subscribed_task) in asyncio.run(_get_subscriptions()):
                if subscribed_task not in updated:
                    asyncio.run(client.delete_subscription(subscription_id=subscription_id))
                    removed.append(subscribed_task)

        return updated, removed
