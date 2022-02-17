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

@receiver(pre_save, sender=models.Routine)
def enqueue_next_routines(sender, instance, **kwargs):
    if not instance.pk:
        return

    current_routine = models.Routine.objects.get(pk=instance.pk)

    if current_routine.status == instance.status:
        return

    if instance.status == models.Routine.Statuses.COMPLETED:
        for routine in instance.next_routines.all():
            routine.enqueue()

@receiver(pre_save, sender=models.Routine)
def revert_previous_routines(sender, instance, **kwargs):
    if not instance.pk:
        return

    current_routine = models.Routine.objects.get(pk=instance.pk)
    if current_routine.status == instance.status:
        return

    if instance.status == models.Routine.Statuses.REVERTED:
        for routine in instance.dependent_routines.all():
            routine.revert()
