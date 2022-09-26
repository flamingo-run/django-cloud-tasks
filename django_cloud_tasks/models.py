# pylint: disable=no-member
from typing import Type

from django.apps import apps
from django.db import models, transaction
from django.utils import timezone

from django_cloud_tasks import serializers


class Pipeline(models.Model):
    name = models.CharField(max_length=100)

    def start(self):
        routines = self.routines.filter(
            models.Q(dependent_routines__id__isnull=True) & models.Q(status=Routine.Statuses.PENDING)
        )
        for routine in routines:
            routine.enqueue()

    def revert(self):
        # TODO: Actually we don't know what to do when a routine with RUNNNING status is triggered
        # to revert. We trust that it will not be a big deal for now. But would be great to support that soon
        routines = self.routines.filter(
            models.Q(next_routines__id__isnull=True) & ~models.Q(status=Routine.Statuses.REVERTED)
        )
        for routine in routines:
            routine.revert()

    def add_routine(self, routine: dict) -> "Routine":
        return self.routines.create(**routine)


class Routine(models.Model):
    class Statuses(models.TextChoices):
        PENDING = ("pending", "Pending")
        SCHEDULED = ("scheduled", "Scheduled")
        RUNNING = ("running", "Running")
        COMPLETED = ("completed", "Completed")
        FAILED = ("failed", "Failed")
        REVERTING = ("reverting", "Reverting")
        REVERTED = ("reverted", "Reverted")

    # TODO: We have a signal to check if task_name defined does exists.
    # We can do it with Django Field Validators
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

    def fail(self, output: dict):
        self.output = output
        self.status = self.Statuses.FAILED
        self.ends_at = timezone.now()
        self.save()

    def complete(self, output: dict):
        self.output = output
        self.status = self.Statuses.COMPLETED
        self.ends_at = timezone.now()
        self.save()

    def enqueue(self):
        with transaction.atomic():
            self.status = self.Statuses.SCHEDULED
            self.starts_at = timezone.now()
            self.save()

    def revert(self):
        with transaction.atomic():
            if self.status not in [self.Statuses.REVERTED, self.Statuses.REVERTING]:
                self.status = self.Statuses.REVERTING
                self.save()

    def add_next(self, routine: dict) -> "Routine":
        routine["pipeline_id"] = self.pipeline_id
        return self.next_routines.create(**routine)

    @property
    def task(self) -> Type["django_cloud_tasks.tasks.Task"] | None:
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
