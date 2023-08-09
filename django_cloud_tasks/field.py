from django.apps import apps
from django.core.exceptions import ValidationError
from django.db.models import CharField

from django_cloud_tasks.apps import DjangoCloudTasksAppConfig
from django_cloud_tasks.exceptions import TaskNotFound


def validate_task_name(value: str):
    app: DjangoCloudTasksAppConfig = apps.get_app_config("django_cloud_tasks")
    try:
        app.get_task(name=value)
    except TaskNotFound as exc:
        raise ValidationError(f"Task {value} not found") from exc


class TaskField(CharField):
    def __init__(self, validate_task: bool = True, **kwargs):
        kwargs.setdefault("max_length", 50)
        super().__init__(**kwargs)
        self.validate_task = validate_task

    def get_db_prep_value(self, value, connection, prepared=False):
        if self.validate_task and value is not None:
            validate_task_name(value=value)
        return super().get_db_prep_value(value, connection, prepared)

    def contribute_to_class(self, cls, name, private_only=False):
        @property
        def get(obj):
            app: DjangoCloudTasksAppConfig = apps.get_app_config("django_cloud_tasks")
            value = getattr(obj, self.attname)
            return app.get_task(name=value)

        field_name = name.replace("_name", "_class")
        setattr(cls, field_name, get)
        return super().contribute_to_class(cls=cls, name=name, private_only=private_only)
