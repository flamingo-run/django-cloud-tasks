import importlib.util
import inspect
import os

from django.apps import AppConfig, apps
from django.conf import settings


class DjangoCloudTasksAppConfig(AppConfig):
    name = 'django_cloud_tasks'
    verbose_name = "Django Cloud Tasks"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tasks = {}
        self.domain = getattr(settings, 'DOMAIN_URL', os.environ.get('DOMAIN_URL', 'http://localhost:8080'))

    def ready(self):
        self.register_tasks()

    def register_tasks(self):
        for app in apps.get_app_configs():
            if app.name.startswith('django.') or app.name == 'django_cloud_tasks':
                continue
            for task_class in self._scan_tasks(app=app):
                self._register_task(task_class=task_class)
        return {}

    def _scan_tasks(self, app):
        from django_cloud_tasks.tasks import BaseTask  # pylint: disable=import-outside-toplevel

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
                if inspect.isclass(klass) and klass is not BaseTask and issubclass(klass, BaseTask):
                    yield klass

    def _register_task(self, task_class):
        self.tasks[task_class.name()] = task_class
