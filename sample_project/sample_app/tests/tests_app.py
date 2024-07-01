import unittest
from unittest.mock import patch
from django_cloud_tasks.apps import DjangoCloudTasksAppConfig
import os


class TestAppConfig(DjangoCloudTasksAppConfig):
    path = os.path.dirname(__file__)


class DjangoCloudTasksAppConfigTest(unittest.TestCase):
    def setUp(self) -> None:
        self.config = TestAppConfig("django_cloud_tasks", "django_cloud_tasks")

    @patch.dict(os.environ, {"DJANGO_CLOUD_TASKS_NAME": "test_string"})
    def test_fetch_str_config(self):
        result = self.config._fetch_str_config("name", "default_value")
        self.assertEqual(result, "test_string")

        with patch.dict(os.environ, {}, clear=True):
            result = self.config._fetch_str_config("name", "default_value")
            self.assertEqual(result, "default_value")

    @patch.dict(os.environ, {"DJANGO_CLOUD_TASKS_NAME": "true"})
    def test_fetch_bool_config(self):
        result = self.config._fetch_bool_config("name", False)
        self.assertEqual(result, True)

        with patch.dict(os.environ, {}, clear=True):
            result = self.config._fetch_bool_config("name", True)
            self.assertEqual(result, True)

    @patch.dict(os.environ, {"DJANGO_CLOUD_TASKS_NAME": "10"})
    def test_fetch_int_config(self):
        result = self.config._fetch_int_config("name", 0)
        self.assertEqual(result, 10)

        with patch.dict(os.environ, {}, clear=True):
            result = self.config._fetch_int_config("name", 5)
            self.assertEqual(result, 5)

    @patch.dict(os.environ, {"DJANGO_CLOUD_TASKS_NAME": "3.14"})
    def test_fetch_float_config(self):
        result = self.config._fetch_float_config("name", 0.0)
        self.assertEqual(result, 3.14)

        with patch.dict(os.environ, {}, clear=True):
            result = self.config._fetch_float_config("name", 2.71)
            self.assertEqual(result, 2.71)

    @patch.dict(os.environ, {"DJANGO_CLOUD_TASKS_NAME": "item1,item2,item3"})
    def test_fetch_list_config(self):
        result = self.config._fetch_list_config("name", [])
        self.assertEqual(result, ["item1", "item2", "item3"])

        with patch.dict(os.environ, {}, clear=True):
            result = self.config._fetch_list_config("name", ["default"])
            self.assertEqual(result, ["default"])
