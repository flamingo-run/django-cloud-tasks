from django.apps import AppConfig


class AnotherAppConfig(AppConfig):
    name = "another_app"

    def ready(self):
        from sample_project.another_app import tasks  # noqa: F401
