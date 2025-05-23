import importlib
import os
from importlib import import_module
from typing import Iterable, Tuple, Any

from django.apps import AppConfig
from django.conf import settings
from django.utils.module_loading import module_has_submodule
from gcp_pilot.pubsub import CloudSubscriber
from gcp_pilot.scheduler import CloudScheduler
from google.api_core.retry import retry_base
from django_cloud_tasks import exceptions

PREFIX = "DJANGO_CLOUD_TASKS_"
DEFAULT_PROPAGATION_HEADERS = ["traceparent"]
DEFAULT_PROPAGATION_HEADERS_KEY = "_http_headers"


class DjangoCloudTasksAppConfig(AppConfig):
    default_auto_field = "django.db.models.AutoField"
    name = "django_cloud_tasks"
    verbose_name = "Django Cloud Tasks"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Tasks
        self.on_demand_tasks = {}
        self.periodic_tasks = {}
        self.subscriber_tasks = {}

        # Routing
        self.domain = self._fetch_str_config(name="ENDPOINT", default="http://localhost:8080")
        self.app_name = self._fetch_str_config(name="APP_NAME", default=os.environ.get("APP_NAME", None))
        self.tasks_url_name = self._fetch_str_config(name="URL_NAME", default="tasks-endpoint")
        self.subscribers_url_name = self._fetch_str_config(
            name="SUBSCRIBERS_URL_NAME", default="subscriptions-endpoint"
        )

        # Execution
        self.eager = self._fetch_bool_config(name="EAGER", default=False)
        self.tasks_max_eta = self._fetch_int_config(name="MAXIMUM_ETA_TASK", default=None)

        # Naming
        self.delimiter = self._fetch_str_config(name="DELIMITER", default="--")

        # Subscriber Retrying
        self.subscribers_max_retries = self._fetch_int_config(name="SUBSCRIBER_MAX_RETRIES", default=None)
        self.subscribers_min_backoff = self._fetch_int_config(name="SUBSCRIBER_MIN_BACKOFF", default=None)
        self.subscribers_max_backoff = self._fetch_int_config(name="SUBSCRIBER_MAX_BACKOFF", default=None)
        self.subscribers_expiration = self._fetch_int_config(name="SUBSCRIBER_EXPIRATION", default=None)

        # Headers
        self.propagated_headers = self._fetch_list_config(
            name="PROPAGATED_HEADERS",
            default=DEFAULT_PROPAGATION_HEADERS,
        )
        self.propagated_headers_key = self._fetch_str_config(
            name="PROPAGATED_HEADERS_KEY",
            default=DEFAULT_PROPAGATION_HEADERS_KEY,
        )

        # Enqueue Retrying
        self.enqueue_retry_exceptions = self._fetch_list_config(
            name="ENQUEUE_RETRY_EXCEPTIONS",
            default=[],
        )
        self.enqueue_retry_initial = self._fetch_float_config(
            name="ENQUEUE_RETRY_INITIAL",
            default=retry_base._DEFAULT_INITIAL_DELAY,
        )
        self.enqueue_retry_maximum = self._fetch_float_config(
            name="ENQUEUE_RETRY_MAXIMUM",
            default=retry_base._DEFAULT_MAXIMUM_DELAY,
        )
        self.enqueue_retry_multiplier = self._fetch_float_config(
            name="ENQUEUE_RETRY_MULTIPLIER",
            default=retry_base._DEFAULT_DELAY_MULTIPLIER,
        )
        self.enqueue_retry_deadline = self._fetch_float_config(
            name="ENQUEUE_RETRY_DEADLINE",
            default=retry_base._DEFAULT_DEADLINE,
        )

    @property
    def task_metadata_class(self):
        return self.get_task_metadata_class()

    def get_tasks(self, only_subscriber: bool = False, only_periodic: bool = False, only_demand: bool = False):
        all_tasks = {
            "demand": list(self.on_demand_tasks.values()),
            "periodic": list(self.periodic_tasks.values()),
            "subscriber": list(self.subscriber_tasks.values()),
        }

        if only_demand:
            return all_tasks["demand"]

        if only_periodic:
            return all_tasks["periodic"]

        if only_subscriber:
            return all_tasks["subscriber"]

        return all_tasks["demand"] + all_tasks["subscriber"] + all_tasks["periodic"]

    def get_task(self, name: str):
        if name in self.on_demand_tasks:
            return self.on_demand_tasks[name]
        if name in self.periodic_tasks:
            return self.periodic_tasks[name]
        if name in self.subscriber_tasks:
            return self.subscriber_tasks[name]
        raise exceptions.TaskNotFound(name=name)

    def get_backup_queue_name(self, original_name: str) -> str:
        return self._fetch_str_config(
            name="BACKUP_QUEUE_NAME",
            default=f"{original_name}{self.delimiter}temp",
        )

    def get_task_metadata_class(self):
        from django_cloud_tasks.tasks import TaskMetadata

        metadata_class_name = self._fetch_str_config(
            name="TASK_METADATA_CLASS",
            default="django_cloud_tasks.tasks.task.TaskMetadata",
        )

        try:
            module_name, class_name = metadata_class_name.rsplit(".", 1)
            module = import_module(module_name)
            metadata_class = getattr(module, class_name)
        except (AttributeError, ImportError, ValueError) as err:
            raise ImportError(f"Unable to import {metadata_class_name}") from err

        if not issubclass(metadata_class, TaskMetadata):
            raise ImportError(f"Class {metadata_class_name} must be a subclass of TaskMetadata")

        return metadata_class

    def _fetch_config(self, name: str, default: Any) -> Any:
        config_name = f"{PREFIX}{name.upper()}"
        return getattr(settings, config_name, os.environ.get(config_name, default))

    def _fetch_str_config(self, name: str, default: Any) -> str:
        value = self._fetch_config(name=name, default=default)
        return str(value) if value is not None else default

    def _fetch_bool_config(self, name: str, default: Any) -> bool:
        value = self._fetch_config(name=name, default=default)
        return str(value).lower() in ("true", "1", "t", "y", "yes") if value is not None else default

    def _fetch_int_config(self, name: str, default: Any) -> int:
        value = self._fetch_config(name=name, default=default)
        return int(value) if value is not None else default

    def _fetch_float_config(self, name: str, default: Any) -> float:
        value = self._fetch_config(name=name, default=default)
        return float(value) if value is not None else default

    def _fetch_list_config(self, name: str, default: Any) -> list:
        value = self._fetch_config(name=name, default=default)

        if not value:
            return default

        if isinstance(value, list):
            return value

        if isinstance(value, str):
            return value.split(",")

        raise ValueError(f"Invalid value for {name}: {value}")

    def register_task(self, task_class):
        from django_cloud_tasks.tasks.periodic_task import PeriodicTask
        from django_cloud_tasks.tasks.subscriber_task import SubscriberTask
        from django_cloud_tasks.tasks.task import Task

        containers = {
            PeriodicTask: self.periodic_tasks,
            SubscriberTask: self.subscriber_tasks,
            Task: self.on_demand_tasks,
        }

        for parent_klass, container in containers.items():
            if issubclass(task_class, parent_klass):
                container[str(task_class)] = task_class
                return
        raise ValueError(f"Unable to defined the task type of {task_class}")

    def schedule_tasks(self) -> Tuple[Iterable[str], Iterable[str], Iterable[str]]:
        client = CloudScheduler()

        def _get_tasks():
            names = []
            if not self.app_name:
                return names
            for job in client.list(prefix=self.app_name):
                schedule_name = job.name.split("/jobs/")[-1]
                names.append((schedule_name.split("--", 1)[-1], schedule_name))
            return names

        expected = self.periodic_tasks.copy()
        existing = dict(_get_tasks())

        to_add = set(expected) - set(existing)
        to_remove = set(existing) - set(expected)
        updated = set(expected) - set(to_add)

        for task_to_add in to_add:
            task_klass = expected[task_to_add]
            task_klass().schedule()

        for task_to_remove in to_remove:
            client.delete(name=existing[task_to_remove])

        return to_add, updated, to_remove

    def set_up_permissions(self):
        sub = CloudSubscriber()
        sub.set_up_permissions(email=sub.credentials.service_account_email)

    def initialize_subscribers(self) -> Tuple[Iterable[str], Iterable[str], Iterable[str]]:
        client = CloudSubscriber()

        def _get_subscriptions():
            names = []
            if not self.app_name:
                return names

            for subscription in client.list_subscriptions(suffix=self.app_name):
                subscription_id = subscription.name.rsplit("subscriptions/", 1)[-1]
                task_name = subscription.push_config.push_endpoint.rsplit("/", 1)[-1]
                names.append((task_name, subscription_id))
            return names

        expected = self.subscriber_tasks.copy()
        existing = dict(_get_subscriptions())

        to_add = set(expected) - set(existing)
        to_remove = set(existing) - set(expected)
        to_update = set(expected) - set(to_add)

        for task_to_add in to_add:
            task_klass = expected[task_to_add]
            task_klass.set_up()

        for task_to_remove in to_remove:
            client.delete_subscription(subscription_id=existing[task_to_remove])

        for task_to_update in to_update:
            task_klass = expected[task_to_update]
            task_klass().set_up()

        return to_add, to_update, to_remove

    def ready(self):
        self.import_signals()

    def import_signals(self) -> None:
        # Same strategy that AppConfig.import_models uses to load app's models
        if module_has_submodule(self.module, "signals"):
            full_module_name = "%s.%s" % (self.name, "signals")
            importlib.import_module(full_module_name)
