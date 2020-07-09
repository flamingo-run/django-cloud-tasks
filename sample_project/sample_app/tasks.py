from django_cloud_tasks.tasks import BaseTask


class CalculatePriceTask(BaseTask):
    def run(self, price, quantity, discount):
        return price * quantity * (1 - discount)


class FailMiserablyTask(BaseTask):
    def run(self, magic_number):
        return magic_number / 0
