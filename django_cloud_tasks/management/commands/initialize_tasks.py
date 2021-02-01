from typing import List

from django_cloud_tasks.management.commands import BaseInitCommand


class Command(BaseInitCommand):
    action = 'configure'
    name = 'tasks'

    def perform_init(self, app_config, *args, **options) -> List[str]:
        report = []
        report.extend(app_config.schedule_tasks())
        report.extend(app_config.initialize_subscribers())
        return report
