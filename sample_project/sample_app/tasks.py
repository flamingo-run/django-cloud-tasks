import abc

from django_cloud_tasks.tasks import PeriodicTask, RoutineTask, SubscriberTask, Task


class BaseAbstractTask(Task, abc.ABC):
    def run(self, **kwargs):
        raise NotImplementedError()  # TODO Allow inheriting from ABC


class AnotherBaseAbstractTask(BaseAbstractTask, abc.ABC):
    def run(self, **kwargs):
        raise NotImplementedError()


class CalculatePriceTask(Task):
    def run(self, price, quantity, discount):
        return price * quantity * (1 - discount)


class ParentCallingChildTask(Task):
    def run(self, price, quantity):
        CalculatePriceTask.asap(price=price, quantity=quantity, discount=0)


class ExposeCustomHeadersTask(Task):
    def run(self):
        return self._metadata.custom_headers


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

    @classmethod
    def topic_name(cls):
        return "potato"

    @classmethod
    def dead_letter_topic_name(cls):
        return None

    def run(self, message: dict, attributes: dict[str, str] | None = None):
        return print(message)


class SayHelloTask(RoutineTask):
    def run(self, **kwargs):
        return {"message": "hello"}

    @classmethod
    def revert(cls, data: dict):
        return {"message": "goodbye"}


class SayHelloWithParamsTask(RoutineTask):
    def run(self, spell: str):
        return {"message": spell}

    @classmethod
    def revert(cls, data: dict):
        return {"message": "goodbye"}
