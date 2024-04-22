from django.apps import AppConfig


class SampleAppConfig(AppConfig):
    name = "sample_app"

    def ready(self):
        from sample_project.sample_app import tasks  # noqa: F401
        from sample_project.sample_app import signals  # noqa: F401
