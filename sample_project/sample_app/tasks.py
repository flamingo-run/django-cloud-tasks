from typing import Dict
from django_cloud_tasks.tasks import Task, PeriodicTask, SubscriberTask, RoutineTask


class BaseAbstractTask(Task):
    abstract = True

    def run(self, **kwargs):
        raise NotImplementedError()  # TODO Allow inheriting from ABC


class AnotherBaseAbstractTask(BaseAbstractTask):
    abstract = True

    def run(self, **kwargs):
        raise NotImplementedError()


class CalculatePriceTask(Task):
    def run(self, price, quantity, discount):
        return price * quantity * (1 - discount)


class FailMiserablyTask(AnotherBaseAbstractTask):
    only_once = True

    def run(self, magic_number):
        return magic_number / 0


class SaySomethingTask(PeriodicTask):
    run_every = "* * * * 1"

    def run(self):
        print("Hello!!")


class PleaseNotifyMeTask(SubscriberTask):
    enable_message_ordering = True

    @property
    def topic_name(self):
        return "potato"

    def run(self, message, attributes):
        return print(message)


class SayHelloTask(RoutineTask):
    def run(self, attributes):
        return {"message": "hello"}

    def revert(self, data: Dict, _meta: Dict, attributes):
        super().revert(data=data, _meta=_meta)
        return {"message": "goodbye"}
