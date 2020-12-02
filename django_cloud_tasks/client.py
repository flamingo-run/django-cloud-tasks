# pylint: disable=not-callable, unsubscriptable-object
import base64
import json
import logging
import os
from datetime import datetime, timedelta

from google import auth
from google.api_core.exceptions import NotFound
from google.cloud import tasks_v2, scheduler
from google.oauth2 import service_account
from google.protobuf import timestamp_pb2

from django_cloud_tasks import exceptions

logger = logging.getLogger(__name__)


DEFAULT_LOCATION = 'us-east1'
DEFAULT_TIMEZONE = 'UTC'


class BaseGoogleCloud:
    _client_class = None
    _scopes = ['https://www.googleapis.com/auth/cloud-platform']

    def __init__(self, subject=None, **kwargs):
        self.credentials = self._build_credentials(subject=subject)
        self.project_name = kwargs.get('project') or self.credentials.project_id

        self.client = self._client_class(
            credentials=self.credentials,
            **kwargs
        )

    @classmethod
    def _build_credentials(cls, subject=None):
        if 'GCP_B64' in os.environ:
            env_var = 'GCP_B64'
            try:
                data = json.loads(base64.b64decode((os.getenv(env_var))))
                credentials = (
                    service_account.Credentials.from_service_account_info(data)
                ).with_scopes(cls._scopes)
            except TypeError as e:
                raise exceptions.GoogleCredentialsException() from e
        else:
            try:
                credentials, _ = auth.default()
            except Exception as e:
                raise exceptions.GoogleCredentialsException() from e

        if subject:
            credentials = credentials.with_subject(subject=subject)

        return credentials

    @property
    def oidc_token(self):
        return {'oidc_token': {'service_account_email': self.credentials.service_account_email}}


class CloudTasksClient(BaseGoogleCloud):
    _client_class = tasks_v2.CloudTasksClient
    DEFAULT_METHOD = tasks_v2.HttpMethod.POST

    def push(self, name, queue, url, payload, method=DEFAULT_METHOD, delay_in_seconds=0):
        parent = self.client.queue_path(self.project_name, queue)

        tasks_v2.Task(
            name=name,
            http_request=tasks_v2.HttpRequest(
                http_method=method,
                url=url,
                body=payload.encode(),
                **self.oidc_token,
            )
        )
        task = {
            'http_request': {
                'http_method': method,
                'url': url,
                'body': payload.encode(),
                **self.oidc_token,
            },
            'name': name,
        }

        if delay_in_seconds:
            target_date = datetime.utcnow() + timedelta(seconds=delay_in_seconds)
            timestamp = timestamp_pb2.Timestamp()
            timestamp.FromDatetime(target_date)

            task.schedule_time = timestamp

        response = self.client.create_task(parent, task)
        return response


class CloudSchedulerClient(BaseGoogleCloud):
    _client_class = scheduler.CloudSchedulerClient
    DEFAULT_METHOD = scheduler.HttpMethod.POST

    def create(
            self,
            name,
            url,
            payload,
            cron,
            timezone=DEFAULT_TIMEZONE,
            method=DEFAULT_METHOD,
            headers=None,
            location=DEFAULT_LOCATION,
    ):
        parent = f"projects/{self.project_name}/locations/{location}"
        job = scheduler.Job(
            name=f'{parent}/jobs/{name}',
            schedule=cron,
            time_zone=timezone,
            http_target=scheduler.HttpTarget(
                uri=url,
                http_method=method,
                body=payload.encode(),
                headers=headers or {},
            )
        )

        response = self.client.create_job(
            request={
                "parent": parent,
                "job": job
            }
        )
        return response

    def update(
            self,
            name,
            url,
            payload,
            cron,
            timezone=DEFAULT_TIMEZONE,
            method=DEFAULT_METHOD,
            headers=None,
            location=DEFAULT_LOCATION,
    ):
        parent = f"projects/{self.project_name}/locations/{location}"
        job = scheduler.Job(
            name=f'{parent}/jobs/{name}',
            schedule=cron,
            time_zone=timezone,
            http_target=scheduler.HttpTarget(
                uri=url,
                http_method=method,
                body=payload.encode(),
                headers=headers or {},
            )
        )

        response = self.client.update_job(
            job=job,
        )
        return response

    def get(self, name, location=DEFAULT_LOCATION):
        response = self.client.get_job(
            name=f"projects/{self.project_name}/locations/{location}/jobs/{name}",
        )
        return response

    def delete(self, name, location=DEFAULT_LOCATION):
        response = self.client.delete_job(
            name=f"projects/{self.project_name}/locations/{location}/jobs/{name}",
        )
        return response

    def put(
            self,
            name,
            url,
            payload,
            cron,
            timezone=DEFAULT_TIMEZONE,
            method=DEFAULT_METHOD,
            headers=None,
            location=DEFAULT_LOCATION,
    ):
        try:
            response = self.update(
                name=name,
                url=url,
                payload=payload,
                cron=cron,
                timezone=timezone,
                method=method,
                headers=headers,
                location=location,
            )
        except NotFound:
            response = self.create(
                name=name,
                url=url,
                payload=payload,
                cron=cron,
                timezone=timezone,
                method=method,
                headers=headers,
                location=location,
            )
        return response
