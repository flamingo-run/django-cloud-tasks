import abc
from functools import lru_cache

from gcp_pilot.scheduler import CloudScheduler

from django_cloud_tasks.serializers import deserialize, serialize
from django_cloud_tasks.tasks.task import Task, get_config, TaskMetadata


class PeriodicTask(Task, abc.ABC):
    run_every: str = None

    @classmethod
    def schedule(cls, **kwargs):
        payload = serialize(kwargs)

        if cls.eager():
            eager_metadata = TaskMetadata.build_eager(task_class=cls)
            return cls(metadata=eager_metadata).run(**deserialize(value=payload))

        return cls._get_scheduler_client().put(
            name=cls.schedule_name(),
            url=cls.url(),
            payload=payload,
            cron=cls.run_every,
        )

    @classmethod
    def schedule_name(cls) -> str:
        name = cls.name()
        if app_name := get_config(name="app_name"):
            delimiter = get_config(name="delimiter")
            name = f"{app_name}{delimiter}{name}"
        return name

    @classmethod
    @lru_cache()
    def _get_scheduler_client(cls) -> CloudScheduler:
        return CloudScheduler()
