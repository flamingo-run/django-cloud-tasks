from typing import List

from django_cloud_tasks.management.commands import BaseInitCommand


class Command(BaseInitCommand):
    action = "schedule"
    name = "tasks"

    def perform_init(self, app_config, *args, **options) -> List[str]:
        added, updated, deleted = app_config.schedule_tasks()

        return (
            [f"[+] {name}" for name in sorted(added)]
            + [f"[-] {name}" for name in sorted(deleted)]
            + [f"[~] {name}" for name in sorted(updated)]
        )
