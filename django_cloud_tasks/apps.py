import os
from typing import List

from django.apps import AppConfig
from django.conf import settings


class DjangoCloudTasksAppConfig(AppConfig):
    name = 'django_cloud_tasks'
    verbose_name = "Django Cloud Tasks"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.on_demand_tasks = {}
        self.periodic_tasks = {}
        self.subscriber_tasks = {}
        self.domain = self._fetch_config(name='DOMAIN_URL', default='http://localhost:8080')

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
            if issubclass(task_class, parent_klass):
                container[task_class.name()] = task_class
                break

    def schedule_tasks(self) -> List[str]:
        report = []
        for task_name, task_klass in self.periodic_tasks.items():
            task_klass().delay()
            report.append(task_name)
        return report

    def initialize_subscribers(self) -> List[str]:
        report = []
        for task_name, task_klass in self.subscriber_tasks.items():
            task_klass().delay()
            report.append(task_name)
        return report
