import logging
from json import JSONDecodeError
from typing import Any

from django.apps import apps
from django.urls import reverse
from gcp_pilot.pubsub import Message

from django_cloud_tasks.apps import DjangoCloudTasksAppConfig

logger = logging.getLogger(__name__)


DJANGO_HEADER_PREFIX = "HTTP_"


class PubSubHeadersMiddleware:
    # Extracts headers from a PubSub message and sets in the request
    def __init__(self, get_response):
        self.get_response = get_response
        app: DjangoCloudTasksAppConfig = apps.get_app_config("django_cloud_tasks")
        self.url_name = app.subscribers_url_name
        self.propagated_headers_key = app.propagated_headers_key

    def __call__(self, request):
        if self.is_subscriber_route(request=request):
            headers = self.extract_headers(request=request)
            request.META.update(
                {f"{DJANGO_HEADER_PREFIX}{key.upper().replace('-', '_')}": value for key, value in headers.items()}
            )

        return self.get_response(request)

    def is_subscriber_route(self, request) -> bool:
        parts = request.path.removesuffix("/").rsplit("/", 1)
        if len(parts) != 2:
            return False

        prefix, task_name = parts
        if not task_name:
            return False

        expected_url = reverse(self.url_name, args=(task_name,))
        return request.path == expected_url

    def extract_headers(self, request) -> dict[str, Any]:
        try:
            message = Message.load(body=request.body)
        except JSONDecodeError:
            logger.warning("Message received through PubSub is not a valid JSON. Ignoring PubSub headers feature.")
            return {}

        headers = {}
        message_headers = message.data.get(self.propagated_headers_key) or {}
        for key, value in message_headers.items():
            headers[key] = value
        return headers
