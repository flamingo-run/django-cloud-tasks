from django_cloud_tasks.tasks import Task, PeriodicTask, SubscriberTask


class CalculatePriceTask(Task):
    def run(self, price, quantity, discount):
        return price * quantity * (1 - discount)


class FailMiserablyTask(Task):
    def run(self, magic_number):
        return magic_number / 0


class SaySomethingTask(PeriodicTask):
    run_every = '* * * * 1'

    def run(self):
        print("Hello!!")


class PleaseNotifyMeTask(SubscriberTask):
    @property
    def topic_name(self):
        return 'potato'

    def run(self, message, attributes):
        return print(message)
