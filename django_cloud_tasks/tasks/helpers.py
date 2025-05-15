from functools import lru_cache
from typing import Any, cast

from django.apps import apps
from django.http import HttpRequest
from django.urls import reverse

from django_cloud_tasks.apps import DjangoCloudTasksAppConfig


@lru_cache
def get_app() -> DjangoCloudTasksAppConfig:
    return cast(DjangoCloudTasksAppConfig, apps.get_app_config("django_cloud_tasks"))


def get_config(name: str) -> Any:
    app = get_app()
    return getattr(app, name)


def is_task_route(request: HttpRequest) -> bool:
    parts = request.path.removesuffix("/").rsplit("/", 1)
    if len(parts) != 2:
        return False

    _, task_name = parts
    if not task_name:
        return False

    expected_url = reverse(get_config(name="tasks_url_name"), args=(task_name,))
    return request.path == expected_url
