import abc

from django.db.models import Model

from django_cloud_tasks.tasks import PeriodicTask, RoutineTask, SubscriberTask, Task, ModelPublisherTask, TaskMetadata
from django_cloud_tasks.exceptions import DiscardTaskException


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
    def build_message_content(cls, obj: Model, event: str, **kwargs) -> dict:
        return {"id": obj.pk, "name": obj.name}

    @classmethod
    def build_message_attributes(cls, obj: Model, event: str, **kwargs) -> dict[str, str]:
        return {"any-custom-attribute": "yay!", "event": event}


class FindPrimeNumbersTask(Task):
    storage: list[int] = []

    @classmethod
    def reset(cls):
        cls.storage = []

    def run(self, quantity):
        if not isinstance(quantity, int):
            raise DiscardTaskException(
                "Can't find a non-integer amount of prime numbers",
                http_status_code=299,
                http_status_reason="Unretriable failure",
            )

        if len(self.storage) >= quantity:
            raise DiscardTaskException("Nothing to do here")

        return self._find_primes(quantity)

    @classmethod
    def _find_primes(cls, quantity: int) -> list[int]:
        if not cls.storage:
            cls.storage = [2]

        while len(cls.storage) < quantity:
            cls.storage.append(cls._find_next_prime(cls.storage[-1] + 1))

        return cls.storage

    @classmethod
    def _find_next_prime(cls, candidate: int) -> int:
        for prime in cls.storage:
            if candidate % prime == 0:
                return cls._find_next_prime(candidate=candidate + 1)

        return candidate


class DummyRoutineTask(RoutineTask):
    def run(self, **kwargs): ...

    @classmethod
    def revert(cls, **kwargs): ...


class MyMetadata(TaskMetadata): ...


class MyUnsupportedMetadata: ...


class RetryEnqueueTask(Task):
    enqueue_retry_exceptions = [
        "google.api_core.exceptions.ServiceUnavailable",
        "google.api_core.exceptions.InternalServerError",
    ]
    enqueue_retry_initial = 0.1
    enqueue_retry_maximum = 10.0
    enqueue_retry_multiplier = 1.3
    enqueue_retry_deadline = 20.0

    def run(self, **kwargs):
        pass
