# pylint: disable=no-member
import logging
from abc import abstractmethod

from django.core.cache import cache

from django_cloud_tasks import models
from django_cloud_tasks.tasks.task import Task

logger = logging.getLogger()


class RoutineTask(Task):
    abstract = True

    @abstractmethod
    def run(self, **kwargs):
        raise NotImplementedError()

    @abstractmethod
    def revert(self, data: dict):
        raise NotImplementedError()


class RoutineLockTaskMixin(Task):
    WAIT_FOR_LOCK = 5  # in seconds
    LOCK_EXPIRATION = 60  # in seconds

    def run(self, routine_id: int):
        lock_key = f"lock-{self.__class__.__name__}-{routine_id}"
        routine_lock = cache.lock(key=lock_key, timeout=self.LOCK_EXPIRATION, blocking_timeout=self.WAIT_FOR_LOCK)
        with routine_lock:
            self._run(routine_id=routine_id)

    @abstractmethod
    def _run(self, routine_id: int):
        raise NotImplementedError()


class PipelineRoutineRevertTask(RoutineLockTaskMixin):
    def _run(self, routine_id: int):
        routine = models.Routine.objects.get(pk=routine_id)
        routine.task().revert(data=routine.output)
        routine.status = models.Routine.Statuses.REVERTED
        routine.save()


class PipelineRoutineTask(RoutineLockTaskMixin):
    def _run(self, routine_id: int):
        routine = models.Routine.objects.get(pk=routine_id)
        if routine.status == models.Routine.Statuses.COMPLETED:
            logger.info(f"Routine #{routine_id} is already completed")
            return

        if routine.max_retries and routine.attempt_count >= routine.max_retries:
            error_message = f"Routine #{routine_id} has exhausted retries and is being reverted"
            logger.info(error_message)
            routine.fail(output={"error": error_message})
            routine.pipeline.revert()
            return

        routine.attempt_count += 1
        routine.status = models.Routine.Statuses.RUNNING
        routine.save()

        try:
            logger.info(f"Routine #{routine_id} is running")
            task_response = routine.task().run(**routine.body)
        except Exception as error:  # pylint: disable=no-member,broad-except
            logger.info(f"Routine #{routine_id} has failed")
            routine.fail(output={"error": str(error)})
            routine.enqueue()
            logger.info(f"Routine #{routine_id} has been enqueued for retry")
            return

        routine.complete(output=task_response)
        logger.info(f"Routine #{routine_id} just completed")
