# pylint: disable=no-member
from datetime import datetime
from typing import Optional, Dict
from django.db import transaction, models
from django.apps import apps
from django_cloud_tasks import tasks, serializers


class Pipeline(models.Model):
    name = models.CharField(max_length=100)

    def start(self):
        routines = self.routines.filter(dependent_routines__id__isnull=True)
        for routine in routines:
            routine.enqueue()

    def revert(self):
        routines = self.routines.filter(next_routines__id__isnull=True)
        for routine in routines:
            routine.revert()


class Routine(models.Model):
    class Statuses(models.TextChoices):
        PENDING = ("pending", "Pending")
        SCHEDULED = ("scheduled", "Scheduled")
        RUNNING = ("running", "Running")
        COMPLETED = ("completed", "Completed")
        FAILED = ("failed", "Failed")
        REVERTING = ("reverting", "Reverting")
        REVERTED = ("reverted", "Reverted")
        ABORTED = ("aborted", "Aborted")

    task_name = models.CharField(max_length=100)
    pipeline = models.ForeignKey(
        to="django_cloud_tasks.Pipeline",
        related_name="routines",
        on_delete=models.PROTECT,
    )
    body = models.JSONField(
        default=dict,
        encoder=serializers.JSONEncoder,
    )
    attempt_count = models.PositiveIntegerField(default=0)
    max_retries = models.PositiveIntegerField(null=True)
    output = models.JSONField(
        null=True,
        blank=True,
        encoder=serializers.JSONEncoder,
    )
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Statuses.choices,
        default=Statuses.PENDING,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )
    next_routines = models.ManyToManyField(
        to="Routine",
        through="RoutineVertex",
        through_fields=("routine", "next_routine"),
        related_name="dependent_routines",
    )

    def fail(self, output: Dict):
        self.output = output
        self.status = self.Statuses.FAILED
        self.ends_at = datetime.now()
        self.save()

    def complete(self, output: Dict):
        self.output = output
        self.status = self.Statuses.COMPLETED
        self.ends_at = datetime.now()
        self.save()

    def enqueue(self):
        with transaction.atomic():
            self.status = self.Statuses.SCHEDULED
            self.starts_at = datetime.now()
            self.save()

    def revert(self):
        with transaction.atomic():
            if self.status == self.Statuses.COMPLETED:
                self.status = self.Statuses.REVERTING
                self.save()
                meta = {"routine_id": self.pk}
                self.task().revert(data=self.output, _meta=meta)
                return

            self.status = self.Statuses.ABORTED
            self.save()

    @property
    def task(self) -> Optional[tasks.Task]:
        app = apps.get_app_config("django_cloud_tasks")
        return app.get_task(name=self.task_name)


class RoutineVertex(models.Model):
    next_routine = models.ForeignKey(
        to="django_cloud_tasks.Routine",
        on_delete=models.PROTECT,
        related_name="required_routine_vertices",
    )
    routine = models.ForeignKey(
        to="django_cloud_tasks.Routine",
        related_name="next_routine_vertices",
        on_delete=models.PROTECT,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(name="unique_routine_next_routine", fields=("next_routine", "routine")),
        ]


__all__ = (
    "Routine",
    "RoutineVertex",
    "Pipeline",
)
