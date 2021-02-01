from typing import List

from django_cloud_tasks.management.commands import BaseInitCommand


class Command(BaseInitCommand):
    action = 'schedule'
    name = 'tasks'

    def add_arguments(self, parser):
        parser.add_argument(
            '--prefix',
            action='store',
            help='Job name prefix to be used to safely detect obsolete jobs',
        )

    def perform_init(self, app_config, *args, **options) -> List[str]:
        prefix = options['prefix']
        updated, deleted = app_config.schedule_tasks(delete_by_prefix=prefix)

        return [f"[+] {name}" for name in updated] + [f"[-] {name}" for name in deleted]
