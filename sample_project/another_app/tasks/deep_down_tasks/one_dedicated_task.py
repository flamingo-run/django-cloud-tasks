from django_cloud_tasks.tasks import BaseTask


class OneBigDedicatedTask(BaseTask):
    def run(self, name):
        return f"Chuck Norris is better than {name}"
