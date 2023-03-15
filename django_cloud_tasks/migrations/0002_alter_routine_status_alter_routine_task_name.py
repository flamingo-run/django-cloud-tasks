# Generated by Django 4.1.7 on 2023-03-15 14:23

from django.db import migrations, models
import django_cloud_tasks.field


class Migration(migrations.Migration):
    dependencies = [
        ("django_cloud_tasks", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="routine",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("scheduled", "Scheduled"),
                    ("running", "Running"),
                    ("completed", "Completed"),
                    ("failed", "Failed"),
                    ("reverting", "Reverting"),
                    ("reverted", "Reverted"),
                ],
                default="pending",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="routine",
            name="task_name",
            field=django_cloud_tasks.field.TaskField(max_length=50),
        ),
    ]
