from django.apps import apps

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Schedule periodic tasks'

    def handle(self, *args, **options):
        apps.get_app_config('django_cloud_tasks').schedule_tasks()
        self.stdout.write(self.style.SUCCESS('Successfully scheduled tasks'))
