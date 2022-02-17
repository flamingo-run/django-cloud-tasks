from django.core.exceptions import ValidationError
from django.db.models.signals import pre_save
from django.dispatch import receiver

from django_cloud_tasks import models, exceptions


@receiver(pre_save, sender=models.Routine)
def ensure_valid_task_name(sender, instance, **kwargs):
    try:
        instance.task
    except exceptions.TaskNotFound:
        raise ValidationError(f"The task {instance.task_name} was not found. Make sure {instance.task_name} is properly set.")
