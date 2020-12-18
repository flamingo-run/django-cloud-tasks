import abc
import importlib.util
import inspect
import os
from typing import List

from django.apps import AppConfig, apps
from django.conf import settings


class DjangoCloudTasksAppConfig(AppConfig):
    name = 'django_cloud_tasks'
    verbose_name = "Django Cloud Tasks"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tasks = {}
        self.subscribers = {}
        self.domain = self._fetch_config(name='DOMAIN_URL', default='http://localhost:8080')
        self.location = self._fetch_config(name='GOOGLE_CLOUD_LOCATION', default='us-east1')

    def _fetch_config(self, name, default):
        return getattr(settings, name, os.environ.get(name, default))

    def ready(self):
        self.register_tasks()

    def register_tasks(self):
        for app in apps.get_app_configs():
            if app.name.startswith('django.') or app.name == 'django_cloud_tasks':
                continue
            for task_class in self._discover_tasks(app=app):
                self._register_task(task_class=task_class)
        return {}

    def _discover_tasks(self, app):
        from django_cloud_tasks.tasks import Task  # pylint: disable=import-outside-toplevel

        files = []

        tasks_file = os.path.join(app.path, 'tasks.py')
        tasks_package = os.path.join(app.path, 'tasks')

        if os.path.exists(tasks_file):
            files.append(tasks_file)
        elif os.path.exists(tasks_package):
            files = []
            for path, _, located_files in os.walk(tasks_package):
                files.extend([
                    os.path.join(path, located_file)
                    for located_file in located_files
                    if located_file != '__init__.py'
                ])

        for file in files:
            name = file.rsplit('/', 1)[0].replace('.py', '')
            spec = importlib.util.spec_from_file_location(name, file)
            foo = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(foo)
            for _, klass in inspect.getmembers(foo):
                is_task = inspect.isclass(klass) and issubclass(klass, Task)
                if not is_task:
                    continue

                is_abstract = abc.ABC in klass.__bases__
                if not is_abstract:
                    yield klass

    def _register_task(self, task_class):
        from django_cloud_tasks.tasks import SubscriberTask  # pylint: disable=import-outside-toplevel

        if issubclass(task_class, SubscriberTask):
            self.subscribers[task_class.name()] = task_class
        else:
            self.tasks[task_class.name()] = task_class

    def schedule_tasks(self) -> List[str]:
        from django_cloud_tasks.tasks import PeriodicTask  # pylint: disable=import-outside-toplevel

        report = []
        for task_name, task_klass in self.tasks.items():
            if issubclass(task_klass, PeriodicTask):
                task_klass().delay()
                report.append(task_name)
        return report

    def initialize_subscribers(self) -> List[str]:
        report = []
        for task_name, task_klass in self.subscribers.items():
            task_klass().delay()
            report.append(task_name)
        return report
