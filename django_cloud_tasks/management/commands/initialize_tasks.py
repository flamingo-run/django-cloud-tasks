from typing import List

from django_cloud_tasks.management.commands import BaseInitCommand


class Command(BaseInitCommand):
    action = 'configure'
    name = 'tasks'

    async def perform_init(self, app_config) -> List[str]:
        report = []
        report.extend(await app_config.schedule_tasks())
        report.extend(await app_config.initialize_subscribers())
        return report
