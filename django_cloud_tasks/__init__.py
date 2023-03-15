default_app_config = "django_cloud_tasks.apps.DjangoCloudTasksAppConfig"


class NotSet:
    def __bool__(self):
        return False


UNSET = NotSet()
