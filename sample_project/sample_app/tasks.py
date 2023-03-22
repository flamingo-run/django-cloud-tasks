import abc

from django.db.models import Model

from django_cloud_tasks.tasks import PeriodicTask, RoutineTask, SubscriberTask, Task, ModelPublisherTask


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
    @classmethod
    def topic_name(cls):
        return "potato"

    @classmethod
    def dead_letter_topic_name(cls):
        return None

    def run(self, content: dict, attributes: dict[str, str] | None = None):
        return content


class ParentSubscriberTask(SubscriberTask):
    @classmethod
    def topic_name(cls):
        return "parent"

    @classmethod
    def dead_letter_topic_name(cls):
        return None

    def run(self, content: dict, attributes: dict[str, str] | None = None):
        CalculatePriceTask.asap(**content)
        return self._metadata.custom_headers


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


class PublishPersonTask(ModelPublisherTask):
    @classmethod
    def build_message_content(cls, obj: Model, **kwargs) -> dict:
        return {"name": obj.name}

    @classmethod
    def build_message_attributes(cls, obj: Model, **kwargs) -> dict[str, str]:
        return {"any-custom-attribute": "yay!"}
