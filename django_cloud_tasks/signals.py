from django.core.exceptions import ValidationError
from django.db.models.signals import pre_save
from django.dispatch import receiver

from django_cloud_tasks import models, exceptions, tasks


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

@receiver(pre_save, sender=models.Routine)
def enqueue_routine_scheduled(sender, instance, **kwargs):
    if not instance.pk:
        return

    current_routine = models.Routine.objects.get(pk=instance.pk)
    if current_routine.status == instance.status:
        return

    if instance.status == models.Routine.Statuses.SCHEDULED:
        tasks.PipelineRoutineTask().delay(routine_id=instance.pk)

@receiver(pre_save, sender=models.Routine)
def ensure_status_machine(sender, instance, **kwargs):
    if not instance.pk and instance.status != models.Routine.Statuses.PENDING:
        raise ValidationError(f"The initial routine's status must be 'pending' not '{instance.status}'")

    if not instance.pk:
        return

    current_routine = models.Routine.objects.get(pk=instance.pk)
    if current_routine.status == instance.status:
        return

    statuses = models.Routine.Statuses
    STATUSES_MACHINE = {
        statuses.PENDING: [None],
        statuses.SCHEDULED: [statuses.PENDING, statuses.FAILED],
        statuses.RUNNING: [statuses.SCHEDULED],
        statuses.COMPLETED: [statuses.RUNNING],
        statuses.ABORTED: [statuses.PENDING],
        statuses.FAILED: [statuses.RUNNING],
        statuses.REVERTING: [statuses.COMPLETED],
        statuses.REVERTED: [statuses.REVERTING],
    }
    available_statuses = STATUSES_MACHINE[instance.status]

    if current_routine.status not in available_statuses:
        raise ValidationError(f"Status update from '{current_routine.status}' to '{instance.status}' is not allowed")

