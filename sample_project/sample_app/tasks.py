from django_cloud_tasks.tasks import Task, PeriodicTask


class CalculatePriceTask(Task):
    def run(self, price, quantity, discount):
        return price * quantity * (1 - discount)


class FailMiserablyTask(Task):
    def run(self, magic_number):
        return magic_number / 0
