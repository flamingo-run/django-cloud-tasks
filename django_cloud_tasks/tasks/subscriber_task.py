import abc
import json
from urllib.parse import urljoin
from typing import Callable

from cachetools.func import lru_cache
from django.urls import reverse
from gcp_pilot.pubsub import CloudSubscriber

from django_cloud_tasks import UNSET
from django_cloud_tasks.tasks.task import Task, get_config


class SubscriberTask(Task, abc.ABC):
    _use_oidc_auth = True
    max_retries: int | None = UNSET
    min_backoff: int | None = UNSET
    max_backoff: int | None = UNSET
    expiration_ttl: int | None = UNSET
    use_cloud_tasks: bool = False

    @abc.abstractmethod
    def run(self, content: dict, attributes: dict[str, str] | None = None):
        raise NotImplementedError()

    @classmethod
    def message_parser(cls) -> Callable:
        # The callable used to parse the message content
        # By default, we handle JSON messages
        return json.loads

    @classmethod
    def set_up(cls):
        return cls._get_subscriber_client().create_or_update_subscription(
            topic_id=cls.topic_name(),
            subscription_id=cls.subscription_name(),
            push_to_url=cls.subscription_url(),
            use_oidc_auth=cls._use_oidc_auth,
            dead_letter_topic_id=cls.dead_letter_topic_name(),
            dead_letter_subscription_id=cls.dead_letter_subscription_name(),
            max_retries=cls.max_retries or get_config("subscribers_max_retries"),
            min_backoff=cls.min_backoff or get_config("subscribers_min_backoff"),
            max_backoff=cls.max_backoff or get_config("subscribers_max_backoff"),
            expiration_ttl=cls.expiration_ttl or get_config("subscribers_expiration"),
            message_filter=cls.subscription_filter(),
        )

    @classmethod
    @abc.abstractmethod
    def topic_name(cls) -> str:
        raise NotImplementedError()

    @classmethod
    def dead_letter_topic_name(cls) -> str | None:
        return None

    @classmethod
    def dead_letter_subscription_name(cls) -> str:
        return cls.dead_letter_topic_name()

    @classmethod
    def subscription_name(cls) -> str:
        name = cls.name()
        if app_name := get_config(name="app_name"):
            delimiter = get_config(name="delimiter")
            name = f"{app_name}{delimiter}{name}"
        return name

    @classmethod
    @lru_cache()
    def subscription_url(cls) -> str:
        domain = get_config(name="domain")
        url_name = get_config(name="subscribers_url_name")
        path = reverse(url_name, args=(cls.name(),))
        return urljoin(domain, path)

    @classmethod
    @lru_cache()
    def _get_subscriber_client(cls) -> CloudSubscriber:
        return CloudSubscriber()

    @classmethod
    def subscription_filter(cls) -> str | None:
        # Reference: https://cloud.google.com/pubsub/docs/subscription-message-filter#filtering_syntax
        return None
