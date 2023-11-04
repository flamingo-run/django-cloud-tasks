import abc
import inspect
from dataclasses import dataclass, fields
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from random import randint
from typing import Any, Self
from urllib.parse import urljoin

from django.apps import apps
from django.urls import reverse
from django.utils.timezone import now
from gcp_pilot.exceptions import DeletedRecently
from gcp_pilot.tasks import CloudTasks
from google.cloud.tasks_v2 import Task as GoogleCloudTask

from django_cloud_tasks.apps import DjangoCloudTasksAppConfig
from django_cloud_tasks.context import get_current_headers
from django_cloud_tasks.serializers import deserialize, serialize
import json


def register(task_class) -> None:
    app: DjangoCloudTasksAppConfig = apps.get_app_config("django_cloud_tasks")
    app.register_task(task_class=task_class)


@dataclass
class TaskMetadata:
    task_id: str
    queue_name: str
    dispatch_number: int  # number of dispatches (0 means first attempt)
    execution_number: int  # number of responses received (excluding 5XX)
    eta: datetime
    previous_response: str | None = None
    previous_failure: str | None = None
    project_id: str | None = None
    custom_headers: dict | None = None
    is_cloud_scheduler: bool | None = None
    cloud_scheduler_schedule_time: datetime | None = None
    cloud_scheduler_job_name: str | None = None

    def __post_init__(self):
        self.custom_headers = get_current_headers()

    @classmethod
    def from_headers(cls, headers: dict) -> Self:
        # Available data: https://cloud.google.com/tasks/docs/creating-http-target-tasks#handler
        cloud_tasks_prefix = "X-Cloudtasks-"
        cloud_scheduler_prefix = "X-Cloudscheduler"

        if (attempt_str := headers.get(f"{cloud_tasks_prefix}Taskexecutioncount")) is not None:
            execution_number = int(attempt_str)
        else:
            execution_number = None

        if (retry_str := headers.get(f"{cloud_tasks_prefix}Taskretrycount")) is not None:
            dispatch_number = int(retry_str)
        else:
            dispatch_number = None

        if eta_epoch := headers.get(f"{cloud_tasks_prefix}Tasketa"):
            eta = datetime.fromtimestamp(int(eta_epoch.split(".")[0]), tz=timezone.utc)
        else:
            eta = None

        cloud_scheduler_job_name = headers.get(f"{cloud_scheduler_prefix}-Jobname")

        if schedule_time_str := headers.get(f"{cloud_scheduler_prefix}-Scheduletime"):
            try:
                schedule_time = datetime.fromisoformat(schedule_time_str)
            except ValueError:
                schedule_time = None
        else:
            schedule_time = None

        is_cloud_scheduler = headers.get(cloud_scheduler_prefix) == "true"

        return cls(
            project_id=headers.get(f"{cloud_tasks_prefix}Projectname"),
            queue_name=headers.get(f"{cloud_tasks_prefix}Queuename"),
            task_id=headers.get(f"{cloud_tasks_prefix}Taskname"),
            dispatch_number=dispatch_number,
            execution_number=execution_number,
            eta=eta,
            previous_response=headers.get(f"{cloud_tasks_prefix}TaskPreviousResponse"),
            previous_failure=headers.get(f"{cloud_tasks_prefix}TaskRetryReason"),
            is_cloud_scheduler=is_cloud_scheduler,
            cloud_scheduler_schedule_time=schedule_time,
            cloud_scheduler_job_name=cloud_scheduler_job_name,
        )

    def to_headers(self) -> dict:
        cloud_tasks_prefix = "X-Cloudtasks-"
        cloud_tasks_headers = {
            f"{cloud_tasks_prefix}Taskname": self.task_id,
            f"{cloud_tasks_prefix}Queuename": self.queue_name,
            f"{cloud_tasks_prefix}Projectname": self.project_id,
            f"{cloud_tasks_prefix}Taskexecutioncount": str(self.execution_number),
            f"{cloud_tasks_prefix}Taskretrycount": str(self.dispatch_number),
            f"{cloud_tasks_prefix}Tasketa": str(int(self.eta.timestamp())),
            f"{cloud_tasks_prefix}TaskPreviousResponse": self.previous_response,
            f"{cloud_tasks_prefix}TaskRetryReason": self.previous_failure,
        }

        if self.is_cloud_scheduler:
            cloud_scheduler_prefix = "X-Cloudscheduler"
            cloud_scheduler_headers = {
                f"{cloud_scheduler_prefix}-Jobname": self.cloud_scheduler_job_name,
                f"{cloud_scheduler_prefix}-Scheduletime": self.cloud_scheduler_schedule_time.isoformat(),
                f"{cloud_scheduler_prefix}": "true",
            }
            return cloud_tasks_headers | cloud_scheduler_headers

        return cloud_tasks_headers

    @classmethod
    def from_task_obj(cls, task_obj: GoogleCloudTask) -> Self:
        _, project_id, _, _, _, queue_name, _, task_id = task_obj.name.split("/")  # TODO: use regex
        return cls(
            project_id=project_id,
            queue_name=queue_name,
            task_id=task_id,
            dispatch_number=task_obj.dispatch_count,
            execution_number=task_obj.response_count,
            eta=task_obj.schedule_time,
            previous_response=None,
            previous_failure=None,
            custom_headers=dict(task_obj.http_request.headers),
        )

    @classmethod
    def build_eager(cls, task_class) -> Self:
        return cls(
            project_id=None,
            queue_name=task_class.queue(),
            task_id="--SYNC--",
            dispatch_number=0,
            execution_number=0,
            eta=now(),
            previous_response=None,
            previous_failure=None,
        )

    @property
    def max_retries(self) -> int:
        queue = CloudTasks(project_id=self.project_id).get_queue(queue_name=self.queue_name)
        return queue.retry_config.max_attempts

    @property
    def attempt_number(self) -> int:
        return self.dispatch_number + 1

    @property
    def first_attempt(self) -> bool:
        return self.dispatch_number == 0

    @property
    def last_attempt(self) -> bool:
        return self.attempt_number == self.max_retries

    @property
    def eager(self) -> bool:
        return self.task_id == "--SYNC--"

    def __eq__(self, other) -> bool:
        if not isinstance(other, TaskMetadata):
            return False

        check_fields = [field.name for field in fields(TaskMetadata)]
        for field in check_fields:
            try:
                value = getattr(self, field)
                other_value = getattr(other, field)
                if value != other_value:
                    return False
            except (AttributeError, ValueError):
                return False
        return True


class TaskMeta(type):
    def __new__(cls, name, bases, attrs):
        klass = type.__new__(cls, name, bases, attrs)
        if not inspect.isabstract(klass) and abc.ABC not in bases:
            register(task_class=klass)
        return klass

    def __str__(self):
        return self.__name__


class DjangoCloudTask(abc.ABCMeta, TaskMeta):
    ...


class Task(abc.ABC, metaclass=DjangoCloudTask):
    only_once: bool = False

    def __init__(self, metadata: TaskMetadata | None = None):
        self._metadata = metadata or TaskMetadata.build_eager(task_class=self.__class__)

    @abc.abstractmethod
    def run(self, **kwargs):
        raise NotImplementedError()

    def process(self, **task_kwargs) -> Any:
        return self.run(**task_kwargs)

    @classmethod
    def sync(cls, **kwargs):
        return cls().run(**kwargs)

    @classmethod
    def asap(cls, **kwargs):
        return cls.push(task_kwargs=kwargs)

    @classmethod
    def later(cls, task_kwargs: dict, eta: int | timedelta | datetime, queue: str = None, headers: dict | None = None):
        if isinstance(eta, int):
            delay_in_seconds = eta
        elif isinstance(eta, timedelta):
            delay_in_seconds = eta.total_seconds()
        elif isinstance(eta, datetime):
            delay_in_seconds = (eta - now()).total_seconds()
        else:
            raise ValueError(
                f"Unsupported schedule {eta} of type {eta.__class__.__name__}. " "Must be int, timedelta or datetime."
            )

        return cls.push(
            task_kwargs=task_kwargs,
            queue=queue,
            headers=headers,
            delay_in_seconds=delay_in_seconds,
        )

    @classmethod
    def until(cls, task_kwargs: dict, max_eta: datetime, queue: str = None, headers: dict | None = None):
        if not isinstance(max_eta, datetime):
            raise ValueError("max_date must be a datetime")
        if max_eta < now():
            raise ValueError("max_date must be in the future")

        max_seconds = (max_eta - now()).total_seconds()
        delay_in_seconds = randint(0, int(max_seconds))
        return cls.push(
            task_kwargs=task_kwargs,
            queue=queue,
            headers=headers,
            delay_in_seconds=delay_in_seconds,
        )

    @classmethod
    def push(
        cls,
        task_kwargs: dict,
        headers: dict | None = None,
        queue: str | None = None,
        delay_in_seconds: int | None = None,
    ):
        payload = serialize(value=task_kwargs)

        if cls.eager():
            return cls.sync(**deserialize(value=payload))

        client = cls._get_tasks_client()

        headers = get_current_headers() | (headers or {})
        headers.setdefault("X-CloudTasks-Projectname", client.project_id)

        api_kwargs = {
            "queue_name": queue or cls.queue(),
            "url": cls.url(),
            "payload": payload,
            "headers": headers,
        }

        if delay_in_seconds:
            api_kwargs["delay_in_seconds"] = delay_in_seconds

        if cls.only_once:
            api_kwargs.update(
                {
                    "task_name": cls.name(),
                    "unique": False,
                }
            )

        try:
            outcome = client.push(**api_kwargs)
        except DeletedRecently:
            # If the task queue was "accidentally" removed, GCP does not let us recreate it in 1 week
            # so we'll use a temporary queue (defined in settings) for some time
            backup_queue_name = apps.get_app_config("django_cloud_tasks").get_backup_queue_name(
                original_name=cls.queue(),
            )
            if not backup_queue_name:
                raise

            api_kwargs["queue_name"] = backup_queue_name
            outcome = cls._get_tasks_client().push(**api_kwargs)

        return TaskMetadata.from_task_obj(task_obj=outcome)

    @classmethod
    def debug(cls, task_id: str):
        client = cls._get_tasks_client()
        task_obj = client.get_task(queue_name=cls.queue(), task_name=task_id)
        task_kwargs = json.loads(task_obj.http_request.body)
        metadata = TaskMetadata.from_task_obj(task_obj=task_obj)
        return cls(metadata=metadata).run(**task_kwargs)

    @classmethod
    def name(cls) -> str:
        return str(cls)

    @classmethod
    def queue(cls) -> str:
        app_name = get_config(name="app_name")
        return app_name or "tasks"

    @classmethod
    @lru_cache()
    def url(cls) -> str:
        domain = get_config(name="domain")
        url_name = get_config(name="tasks_url_name")
        path = reverse(url_name, args=(cls.name(),))
        return urljoin(domain, path)

    @classmethod
    @lru_cache()
    def eager(cls) -> bool:
        return get_config(name="eager")

    @classmethod
    @lru_cache()
    def _get_tasks_client(cls) -> CloudTasks:
        return CloudTasks()


def get_config(name: str) -> Any:
    app: DjangoCloudTasksAppConfig = apps.get_app_config("django_cloud_tasks")
    return getattr(app, name)
