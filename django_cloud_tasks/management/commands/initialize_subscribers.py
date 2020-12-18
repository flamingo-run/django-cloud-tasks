from typing import List

from django_cloud_tasks.management.commands import BaseInitCommand


class Command(BaseInitCommand):
    name = 'subscribers'

    def perform_init(self, app_config) -> List[str]:
        return app_config.initialize_subscribers()
