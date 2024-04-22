from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from sample_app import models, tasks


@receiver(post_save, sender=models.Person)
def publish_person(sender, instance: models.Person, **kwargs):
    tasks.PublishPersonTask.sync_on_commit(obj=instance, event="saved")


@receiver(post_delete, sender=models.Person)
def delete_person(sender, instance: models.Person, **kwargs):
    tasks.PublishPersonTask.sync_on_commit(obj=instance, event="deleted")
