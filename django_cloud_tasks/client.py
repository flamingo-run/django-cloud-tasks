# pylint: disable=not-callable, unsubscriptable-object
import base64
import json
import logging
import os
from datetime import datetime, timedelta

from google.cloud import tasks_v2
from google.oauth2 import service_account
from google.protobuf import timestamp_pb2

from django_cloud_tasks import exceptions

logger = logging.getLogger(__name__)


class BaseGoogleCloud:
    _config = None
    _credentials = None
    _client_class = None
    _scopes = ['https://www.googleapis.com/auth/cloud-platform']

    def __init__(self, subject=None, **kwargs):
        config = self.config()
        self.project_name = kwargs.get('project') or config.get('project_id')

        # if the client is sending an empty project,
        # override the project parameter to avoid GCloud SDK to auto-detect it
        if 'project' in kwargs and kwargs.get('project') is None:
            kwargs['project'] = self.project_name

        self.client = self._client_class(
            credentials=self.credentials(subject=subject),
            **kwargs
        )

    @classmethod
    def credentials(cls, subject=None):
        if not cls._credentials:
            cls._credentials = (
                service_account.Credentials.from_service_account_info(cls.config())
            ).with_scopes(cls._scopes)
            if subject:
                cls._credentials = cls._credentials.with_subject(subject=subject)
        return cls._credentials

    @classmethod
    def encode_credential(cls, json_str):
        return base64.b64encode(json_str.encode()).decode()

    @classmethod
    def config(cls):
        if not cls._config:
            if 'GCP_B64' in os.environ:
                def _b64(v):
                    return json.loads(base64.b64decode(v))

                func = _b64
                env_var = 'GCP_B64'
            else:
                func = json.loads
                env_var = 'GCP_JSON'

            try:
                cls._config = func(os.getenv(env_var))
            except TypeError:
                raise exceptions.GoogleCredentialsException()
        return cls._config


class CloudTasksClient(BaseGoogleCloud):
    _client_class = tasks_v2.CloudTasksClient

    def push(self, name, queue, url, payload, delay_in_seconds=0):
        parent = self.client.queue_path(self.project_name, queue)

        task = {
            'http_request': {
                'http_method': 'POST',
                'url': url,
                'body': payload.encode(),
                'oidc_token': {
                    'service_account_email': self.config()['client_email'],
                }
            },
            'name': name,
        }

        if delay_in_seconds:
            target_date = datetime.utcnow() + timedelta(seconds=delay_in_seconds)
            timestamp = timestamp_pb2.Timestamp()
            timestamp.FromDatetime(target_date)

            task['schedule_time'] = timestamp

        response = self.client.create_task(parent, task)
        return response
