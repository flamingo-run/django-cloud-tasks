import factory
from django.db.models.signals import post_save, pre_save

from django_cloud_tasks.models import Pipeline, Routine, RoutineVertex


class PipelineFactory(factory.django.DjangoModelFactory):
    name = factory.Faker("sentence")

    class Meta:
        model = Pipeline


class RoutineFactory(factory.django.DjangoModelFactory):
    task_name = "DummyRoutineTask"
    pipeline = factory.SubFactory(PipelineFactory)

    class Meta:
        model = Routine


@factory.django.mute_signals(post_save, pre_save)
class RoutineWithoutSignalFactory(RoutineFactory):
    ...


class RoutineVertexFactory(factory.django.DjangoModelFactory):
    next_routine = factory.SubFactory(RoutineFactory)
    routine = factory.SubFactory(RoutineFactory)

    class Meta:
        model = RoutineVertex
