import abc
from typing import List

from django.apps import apps
from django.core.management.base import BaseCommand


class BaseInitCommand(BaseCommand, abc.ABC):
    action = "initialize"
    name = None

    @property
    def help(self):
        return f"{self.action} {self.name}".title()

    @abc.abstractmethod
    def perform_init(self, app_config, *args, **options) -> List[str]:
        raise NotImplementedError()

    def handle(self, *args, **options):
        app_config = apps.get_app_config("django_cloud_tasks")
        report = self.perform_init(app_config=app_config, *args, **options)

        n = len(report)
        report_str = "\n".join([f"- {name}" for name in report])

        message = f"Successfully {self.action}d {n} {self.name} to domain {app_config.domain}\n{report_str}"
        self.stdout.write(self.style.SUCCESS(message))
