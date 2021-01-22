from django.apps import AppConfig


class AnotherAppConfig(AppConfig):
    name = 'another_app'

    def ready(self):
        from another_app import tasks  # pylint: disable=import-outside-toplevel,unused-import
