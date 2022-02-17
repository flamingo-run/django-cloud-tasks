# pylint: disable=no-member
from abc import abstractmethod
from gcp_pilot.pubsub import CloudSubscriber, Message

from django_cloud_tasks.helpers import run_coroutine
from django_cloud_tasks import tasks


class SubscriberTask(tasks.Task):
    abstract = True
    _use_oidc_auth = True
    _url_name = "subscriptions-endpoint"
    enable_message_ordering = False

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
        return run_coroutine(
            handler=self.__client.create_or_update_subscription,
            topic_id=self.topic_name,
            subscription_id=self.subscription_name,
            enable_message_ordering=self.enable_message_ordering,
            push_to_url=self.url(),
            use_oidc_auth=self._use_oidc_auth,
        )

    @property
    @abstractmethod
    def topic_name(self):
        raise NotImplementedError()

    @property
    def subscription_name(self):
        return f"{self.topic_name}{self._delimiter}{self._app_name or self.name()}"

    @property
    def __client(self):
        return CloudSubscriber()
