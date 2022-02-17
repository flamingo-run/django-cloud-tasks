from django.models import Q

from django_cloud_tasks import models, tasks


class RoutineTask(tasks.Task):
    def run(self, routine_id: int):
        # WIP: lock task
        routine = models.Routine.objects.get(pk=routine_id)
        if routine.status == models.Routine.Statuses.COMPLETED:
            self._run_next_routines(routine=routine)
            return

        if self._exists_pending_routine(routine=routine):
            routine.enqueue()
            return

        if routine.max_retries and routine.attempt_count >= routine.max_retries:
            routine.fail(output="Retry exhausted")
            # should we append routine_id into exhausted_task_body?
            routine.get_exhausted_task().run(**routine.exhausted_task_body)
            return

        routine.attempt_count += 1
        routine.save()

        try:
            routine.task().run(**routine.body)
        except Exception as e:
            routine.fail(output=str(e))
            routine.enqueue()
            return

        routine.complete()
        self._run_next_routines(routine=routine)

    def _run_next_routines(self, routine):
        for next_routine in routine.next_routines.all():
            RoutineTask().delay(routine_id=next_routine.pk)

    def _exists_pending_routine(self, routine: "models.Routine") -> bool:
        return routine.previous_routines.filter(~Q(status=models.Routine.Statuses.COMPLETED)).exists()
