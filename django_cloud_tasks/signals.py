from django.core.exceptions import ValidationError
from django.db.models.signals import pre_save
from django.dispatch import receiver

from django_cloud_tasks import models


def _is_status_changing(instance: models.Routine) -> bool:
    if not instance.pk:
        return False

    current_routine = models.Routine.objects.get(pk=instance.pk)
    return current_routine.status != instance.status


def enqueue_next_routines(instance: models.Routine):
    for routine in instance.next_routines.all():
        routine.enqueue()


def revert_previous_routines(instance: models.Routine):
    for routine in instance.dependent_routines.all():
        routine.revert()


def enqueue_routine_scheduled(instance: models.Routine):
    from django_cloud_tasks.tasks import RoutineExecutorTask

    RoutineExecutorTask.asap(routine_id=instance.pk)


def enqueue_revert_task(instance: models.Routine):
    from django_cloud_tasks.tasks import RoutineReverterTask

    RoutineReverterTask.asap(routine_id=instance.pk)


STATUS_ACTION = {
    models.Routine.Statuses.COMPLETED: enqueue_next_routines,
    models.Routine.Statuses.REVERTED: revert_previous_routines,
    models.Routine.Statuses.SCHEDULED: enqueue_routine_scheduled,
    models.Routine.Statuses.REVERTING: enqueue_revert_task,
}


@receiver(pre_save, sender=models.Routine)
def handle_status_changed(sender, instance: models.Routine, **kwargs):
    if not _is_status_changing(instance=instance):
        return

    if action := STATUS_ACTION.get(instance.status):
        action(instance=instance)


@receiver(pre_save, sender=models.Routine)
def ensure_status_machine(sender, instance: models.Routine, **kwargs):
    if not instance.pk and instance.status != models.Routine.Statuses.PENDING:
        raise ValidationError(f"The initial routine's status must be 'pending' not '{instance.status}'")

    if not _is_status_changing(instance=instance):
        return

    current_routine = models.Routine.objects.get(pk=instance.pk)

    statuses = models.Routine.Statuses
    machine_statuses = {
        statuses.PENDING: [None],
        statuses.SCHEDULED: [statuses.PENDING, statuses.FAILED],
        statuses.RUNNING: [statuses.SCHEDULED],
        statuses.COMPLETED: [statuses.RUNNING],
        statuses.FAILED: [statuses.RUNNING, statuses.SCHEDULED],
        statuses.REVERTING: [statuses.COMPLETED, statuses.PENDING, statuses.SCHEDULED, statuses.FAILED],
        statuses.REVERTED: [statuses.REVERTING],
    }
    available_statuses = machine_statuses[instance.status]

    if current_routine.status not in available_statuses:
        raise ValidationError(f"Status update from '{current_routine.status}' to '{instance.status}' is not allowed")
