# TaskField - Storing Task References in Models

Django Cloud Tasks provides a custom Django model field, `django_cloud_tasks.field.TaskField`, designed to store a reference to a specific task class name within your models. This is particularly useful when you want to dynamically determine which task to run based on a model instance's data.

## Overview

The `TaskField` is a subclass of Django's `CharField`. It stores the string representation of a task class (e.g., `"MyCoolTask"` or `"myapp.tasks.AnotherTask"` if it's not auto-discoverable by simple name).

Key features:

*   **Validation:** It can automatically validate that the stored string corresponds to an actual task class registered with Django Cloud Tasks.
*   **Convenient Class Access:** It dynamically adds a property to your model that allows you to directly access the task class itself from the stored name.

## Usage

Here's how you might use `TaskField` in one of your models:

```python
# In your app's models.py
from django.db import models
from django_cloud_tasks.field import TaskField

class NotificationRule(models.Model):
    name = models.CharField(max_length=100)
    event_type = models.CharField(max_length=50, unique=True)

    # Stores the name of the task to execute for this event type
    task_to_run_name = TaskField()
    # If you don't want validation at the DB level (e.g. during migrations before tasks are loaded):
    # task_to_run_name = TaskField(validate_task=False)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} (Event: {self.event_type} -> Task: {self.task_to_run_name})"

    def trigger_action(self, payload: dict):
        if self.is_active and self.task_to_run_name:
            # Access the actual task class via the dynamically added property
            # If your field is `foo_name`, the property is `foo_class`
            ActualTaskClass = self.task_to_run_class
            if ActualTaskClass:
                print(f"Triggering task {ActualTaskClass.name()} for event {self.event_type}")
                ActualTaskClass.asap(**payload)
            else:
                print(f"No valid task class found for {self.task_to_run_name}")
```

In this example:

1.  `task_to_run_name = TaskField()` defines a field that will store the name of a task (e.g., `"SendWelcomeEmailTask"`).
2.  When you save a `NotificationRule` instance, if `validate_task` is `True` (the default), the field will check if the provided string name corresponds to a task discoverable by `django-cloud-tasks`.
3.  A dynamic property `task_to_run_class` is automatically added to your `NotificationRule` model. Accessing `my_rule.task_to_run_class` will return the actual task class (e.g., `SendWelcomeEmailTask`), not just its name.

## Field Options

*   **`validate_task: bool = True`**
    *   If `True` (default), the field will validate that the provided task name corresponds to a registered task class when the value is being prepared for the database. This helps ensure data integrity.
    *   If `False`, this validation is skipped. This might be useful in scenarios like during initial data migrations where tasks might not be fully loaded or discoverable yet.
*   **`max_length: int = 50`**
    *   The default `max_length` for the underlying `CharField`. You can override this if your task names are longer (though 50 characters is usually sufficient for a class name).
*   Other `CharField` options (like `null`, `blank`, `default`, `help_text`, etc.) can also be used.

## How the Class Property Works

When you define a field like `my_task_field_name = TaskField()`, the `TaskField` automatically adds a new property to your model named `my_task_field_class`.

So, if your field is `task_to_run_name`, the property becomes `task_to_run_class`.
If your field is `backup_task_name`, the property becomes `backup_task_class`.

This makes it very convenient to work with, as you can directly call class methods like `.asap()`, `.sync()`, or `.later()` on the retrieved class.

## Use Cases

*   **Configurable Workflows:** Allow administrators or users to select different tasks for different events or conditions through a Django admin interface or a settings model.
*   **Dynamic Task Routing:** In a system that processes various types of jobs, a model instance can hold a reference to the specific task class responsible for handling its job type.
*   **Scheduled Task Management:** If you have a model that defines custom schedules, it could also store the name of the task to be executed on that schedule.

`TaskField` simplifies storing and retrieving task references in your database, adding a layer of validation and convenience. 