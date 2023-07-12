import abc
import logging

from django.core.cache import cache

from django_cloud_tasks import models
from django_cloud_tasks.tasks.task import Task

logger = logging.getLogger()


class RoutineTask(Task, abc.ABC):
    @classmethod
    @abc.abstractmethod
    def revert(cls, data: dict):
        raise NotImplementedError()


class PipelineDispatcherTask(Task, abc.ABC):
    WAIT_FOR_LOCK = 5  # in seconds
    LOCK_EXPIRATION = 60  # in seconds

    def run(self, routine_id: int):
        lock_key = f"lock-{self.__class__.__name__}-{routine_id}"
        routine_lock = cache.lock(key=lock_key, timeout=self.LOCK_EXPIRATION, blocking_timeout=self.WAIT_FOR_LOCK)
        with routine_lock:
            routine = models.Routine.objects.get(pk=routine_id)
            return self.process_routine(routine=routine)

    @abc.abstractmethod
    def process_routine(self, routine: models.Routine):
        raise NotImplementedError()


class RoutineReverterTask(PipelineDispatcherTask):
    def process_routine(self, routine: models.Routine):
        routine.task_class.revert(data=routine.output)
        routine.status = models.Routine.Statuses.REVERTED
        routine.save(update_fields=("status",))


class RoutineExecutorTask(PipelineDispatcherTask):
    def process_routine(self, routine: models.Routine):
        if routine.status == models.Routine.Statuses.COMPLETED:
            logger.info(f"Routine #{routine.pk} is already completed")
            return

        if routine.attempt_count >= routine.max_retries:
            error_message = f"Routine #{routine.pk} has exhausted retries and is being reverted"
            logger.info(error_message)
            routine.fail(output={"error": error_message})
            routine.pipeline.revert()
            return

        routine.attempt_count += 1
        routine.status = models.Routine.Statuses.RUNNING
        routine.save(update_fields=("attempt_count", "status", "updated_at"))

        try:
            logger.info(f"Routine #{routine.pk} is running")
            task_response = routine.task_class(metadata=self._metadata).sync(**routine.body)
        except Exception as error:
            logger.info(f"Routine #{routine.pk} has failed")

            routine.fail(output={"error": str(error)})
            logger.info(f"Routine #{routine.pk} is being enqueued to retry")
            routine.enqueue()
            return

        routine.complete(output=task_response)
        logger.info(f"Routine #{routine.pk} just completed")
