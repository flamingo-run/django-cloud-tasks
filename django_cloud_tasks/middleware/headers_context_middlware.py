import logging
from typing import Any

from django.apps import apps

from django_cloud_tasks.apps import DjangoCloudTasksAppConfig
from django_cloud_tasks.context import reset_current_headers, set_current_headers

logger = logging.getLogger(__name__)


class HeadersContextMiddleware:
    # Adds a global context with the headers received in the request.
    # This context can be used to propagate headers in tasks/publishers
    def __init__(self, get_response):
        self.get_response = get_response

        app: DjangoCloudTasksAppConfig = apps.get_app_config("django_cloud_tasks")
        self.allowed_headers = [header.lower() for header in app.propagated_headers]

    def __call__(self, request):
        headers = self.extract_headers(request=request)

        ctx_token = set_current_headers(headers)
        response = self.get_response(request)
        reset_current_headers(ctx_token)

        return response

    def extract_headers(self, request) -> dict[str, Any]:
        all_headers = dict(request.headers)
        filtered_headers = {key: value for key, value in all_headers.items() if key.lower() in self.allowed_headers}
        return filtered_headers
