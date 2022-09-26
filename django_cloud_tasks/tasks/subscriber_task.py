# pylint: disable=no-member
from abc import abstractmethod

from gcp_pilot.pubsub import CloudSubscriber, Message

from django_cloud_tasks.tasks.task import Task


class SubscriberTask(Task):
    abstract = True
    _use_oidc_auth = True
    _url_name = "subscriptions-endpoint"
    enable_message_ordering: bool = False
    max_retries: int | None = None
    min_backoff: int | None = None
    max_backoff: int | None = None
    expiration_ttl: int | None = None

    def _body_to_kwargs(self, request_body):
        message = Message.load(body=request_body)
        return {
            "message": message.data,
            "attributes": message.attributes,
        }

    @abstractmethod
    def run(self, message, attributes):
        raise NotImplementedError()

    def register(self):
        return self.__client.create_or_update_subscription(
            topic_id=self.topic_name,
            subscription_id=self.subscription_name,
            enable_message_ordering=self.enable_message_ordering,
            push_to_url=self.url(),
            use_oidc_auth=self._use_oidc_auth,
            dead_letter_topic_id=self.dead_letter_topic_name,
            dead_letter_subscription_id=self.dead_letter_subscription_name,
            max_retries=self.max_retries,
            min_backoff=self.min_backoff,
            max_backoff=self.max_backoff,
            expiration_ttl=self.expiration_ttl,
        )

    @property
    @abstractmethod
    def topic_name(self):
        raise NotImplementedError()

    @property
    def dead_letter_topic_name(self):
        return None

    @property
    def dead_letter_subscription_name(self):
        return self.dead_letter_topic_name

    @property
    def subscription_name(self):
        return f"{self.topic_name}{self._delimiter}{self._app_name or self.name()}"

    @property
    def __client(self):
        return CloudSubscriber()
