# Generated by Django 4.0.2 on 2022-02-23 00:09

import django.db.models.deletion
from django.db import migrations, models

import django_cloud_tasks.serializers


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Pipeline",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100)),
            ],
        ),
        migrations.CreateModel(
            name="Routine",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("task_name", models.CharField(max_length=100)),
                ("body", models.JSONField(default=dict, encoder=django_cloud_tasks.serializers.JSONEncoder)),
                ("attempt_count", models.PositiveIntegerField(default=0)),
                ("max_retries", models.PositiveIntegerField(null=True)),
                ("output", models.JSONField(blank=True, encoder=django_cloud_tasks.serializers.JSONEncoder, null=True)),
                ("starts_at", models.DateTimeField(blank=True, null=True)),
                ("ends_at", models.DateTimeField(blank=True, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("scheduled", "Scheduled"),
                            ("running", "Running"),
                            ("completed", "Completed"),
                            ("failed", "Failed"),
                            ("reverting", "Reverting"),
                            ("reverted", "Reverted"),
                            ("aborted", "Aborted"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="RoutineVertex",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "next_routine",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="required_routine_vertices",
                        to="django_cloud_tasks.routine",
                    ),
                ),
                (
                    "routine",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="next_routine_vertices",
                        to="django_cloud_tasks.routine",
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="routine",
            name="next_routines",
            field=models.ManyToManyField(
                related_name="dependent_routines",
                through="django_cloud_tasks.RoutineVertex",
                to="django_cloud_tasks.Routine",
            ),
        ),
        migrations.AddField(
            model_name="routine",
            name="pipeline",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name="routines", to="django_cloud_tasks.pipeline"
            ),
        ),
        migrations.AddConstraint(
            model_name="routinevertex",
            constraint=models.UniqueConstraint(fields=("next_routine", "routine"), name="unique_routine_next_routine"),
        ),
    ]
