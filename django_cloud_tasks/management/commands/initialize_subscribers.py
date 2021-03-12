from typing import List

from django_cloud_tasks.management.commands import BaseInitCommand


class Command(BaseInitCommand):
    name = 'subscribers'

    def perform_init(self, app_config, *args, **options) -> List[str]:
        updated, deleted = app_config.initialize_subscribers()
        return [f"[+] {name}" for name in updated] + [f"[-] {name}" for name in deleted]
