![Github CI](https://github.com/flamingo-run/django-cloud-tasks/workflows/Github%20CI/badge.svg)
[![Maintainability](https://api.codeclimate.com/v1/badges/4e211a8dc7a2520873c6/maintainability)](https://codeclimate.com/github/flamingo-run/django-cloud-tasks/maintainability)
[![Test Coverage](https://api.codeclimate.com/v1/badges/4e211a8dc7a2520873c6/test_coverage)](https://codeclimate.com/github/flamingo-run/django-cloud-tasks/test_coverage)
[![python](https://img.shields.io/badge/python-3.11-blue.svg)]()
[![python](https://img.shields.io/badge/python-3.12-blue.svg)]()
[![python](https://img.shields.io/badge/python-3.13-blue.svg)]()

# Django Cloud Tasks

Powered by [GCP Pilot](https://github.com/flamingo-run/gcp-pilot).

## Installation

`pip install django-google-cloud-tasks`

## APIs

The following APIs must be enabled in your project(s):

- [Cloud Tasks API](https://console.cloud.google.com/marketplace/product/google/cloudtasks.googleapis.com)
- [Cloud Scheduler API](https://console.cloud.google.com/marketplace/product/google/cloudscheduler.googleapis.com)
- [Admin SDK API](https://console.cloud.google.com/marketplace/product/google/admin.googleapis.com)

### IAM

TDB

## Configuration

Include the Django app in your settings.py:

```
INSTALLED_APPS = [
    # ...
    "django_cloud_tasks",
    # ...
]
```

> Add ``DJANGO_CLOUD_TASKS_ENDPOINT`` to your Django settings or as an environment variable

![image](https://user-images.githubusercontent.com/9717144/100749131-00cce780-33c3-11eb-8f2a-b465bc0a45bb.png)

Additionally, you can configure with more settings or environment variables:

- `DJANGO_CLOUD_TASKS_APP_NAME`: uses this name as the queue name, prefix to topics and subscriptions. Default: `None`.
- `DJANGO_CLOUD_TASKS_DELIMITER`: uses this name as delimiter to the `APP_NAME` and the topic/subscription name. Default: `--`.
- `DJANGO_CLOUD_TASKS_EAGER`: force the tasks to always run synchronously. Useful for local development. Default: `False`.
- `DJANGO_CLOUD_TASKS_URL_NAME`: Django URL-name that process On Demand tasks. We provide a view for that, but if you want to create your own, set this value. Default: `tasks-endpoint`.
- `DJANGO_CLOUD_TASKS_SUBSCRIBERS_URL_NAME`: Django URL-name that process Subscribers. We provide a view for that, but if you want to create your own, set this value. Default: `subscriptions-endpoint`.
- `DJANGO_CLOUD_TASKS_PROPAGATED_HEADERS`: . Default: `["traceparent"]`.
- `DJANGO_CLOUD_TASKS_PROPAGATED_HEADERS_KEY`: when propagating headers in PubSub, use a key to store the values in the Message data. Default: `_http_headers`.
- `DJANGO_CLOUD_TASKS_MAXIMUM_ETA_TASK`: maximum time in seconds to schedule a task in the future. Default: `None`. In [GCP documentation](https://cloud.google.com/tasks/docs/quotas) the maximum schedule time for a task is 30 days from current date and time.

## On Demand Task

Tasks can be executed on demand, asynchronously or synchronously.

The service used is Google Cloud Tasks:

```python
from django_cloud_tasks.tasks import Task


class MyTask(Task):
    def run(self, x, y):
        # computation goes here
        print(x**y)


MyTask.asap(x=10, y=3)  # run async (another instance will execute and print)
MyTask.sync(x=10, y=5)  # run sync (the print happens right now)
```

It's also possible to execute asynchronously, but not immediately:
```python
MyTask.later(task_kwargs=dict(x=10, y=5), eta=3600)  # run async in 1 hour (int, timedelta and datetime are accepted)

MyTask.until(task_kwargs=dict(x=10, y=5), eta=3600)  # run async up to 1 hour, decided randomly (int, timedelta and datetime are accepted)
```

All of these call methods are wrappers to the fully customizable method `push`, which supports overriding queue name, headers and more:
```python
MyTask.push(task_kwargs=dict(x=10, y=5), **kwargs)  # run async, but deeper customization is available
```

### Queue

When executing an async task, a new job will be added to a queue in Cloud Tasks to be processed by another Cloud Run instance.

You can choose this queue's name in the following order:
- Overriding manually when scheduling with `push`, `until` or `later`
- Defining `DJANGO_CLOUD_TASKS_APP_NAME` in Django settings
- otherwise, `tasks` will be used as queue name

It's also possible to set dynamically with:

```python
from django_cloud_tasks.tasks import Task


class MyTask(Task):
    @classmethod
    def queue(cls) -> str:
        return "my-queue-name-here"
```

### Troubleshooting

When a task if failing in Cloud Tasks and you want to debug **locally** with the same data, 
you can get the task ID from Cloud Task UI (the big number in the column NAME) and run the task locally with the same parameters with:

```python
MyTask.debug(task_id="<the task number>")
```

### Cleanup

Google Cloud Tasks will automatically discard any jobs after the max-retries.

If by any reason you need to discard jobs manually, you can provide the Task ID:


```python
MyTask.discard(task_id="<the task number>")
```

Or you can batch discard many tasks at once:


```python
MyTask.discard()
```


You can also provide `min_retries` parameter to filter the tasks that have retried at least some amount 
(so tasks have some chance to execute):

```python
MyTask.discard(min_retries=5)
```

### Task Enqueuing Retry Policy

When enqueuing tasks with the Cloud Tasks API, transient errors (network issues, service unavailable responses, etc.) can cause task creation to fail silently. Since there is no automatic retry for the API calls that enqueue tasks, this can lead to tasks never being created, potentially breaking workflows or causing data inconsistency.

You can configure a retry policy to automatically handle these transient failures when tasks are being enqueued.

#### Global Configuration

Configure the retry policy globally in your Django settings:

```python
# settings.py

# Comma-separated list of exception classes that should trigger a retry
# Default: None (no retry will be performed)
DJANGO_CLOUD_TASKS_ENQUEUE_RETRY_EXCEPTIONS = "google.api_core.exceptions.ServiceUnavailable,google.api_core.exceptions.InternalServerError"

# Initial retry delay in seconds
# Default: 1.0  # seconds
DJANGO_CLOUD_TASKS_ENQUEUE_RETRY_INITIAL = 0.1

# Maximum retry delay in seconds
# Default: 60.0  # seconds
DJANGO_CLOUD_TASKS_ENQUEUE_RETRY_MAXIMUM = 10.0

# Multiplier applied to the delay between retries
# Default: 2.0
DJANGO_CLOUD_TASKS_ENQUEUE_RETRY_MULTIPLIER = 1.3

# Maximum total time spent retrying in seconds
# Default: 120.0  # seconds
DJANGO_CLOUD_TASKS_ENQUEUE_RETRY_DEADLINE = 20.0
```

#### Task-Specific Configuration

Override the retry policy for specific task classes:

```python
from django_cloud_tasks.tasks import Task

class MyTask(Task):
    # List of exception classes that should trigger a retry
    enqueue_retry_exceptions = [
        "google.api_core.exceptions.ServiceUnavailable",
        "google.api_core.exceptions.InternalServerError",
    ]
    
    # Initial retry delay in seconds
    enqueue_retry_initial = 0.1
    
    # Maximum retry delay in seconds
    enqueue_retry_maximum = 10.0
    
    # Multiplier applied to the delay between retries
    enqueue_retry_multiplier = 1.3
    
    # Maximum total time spent retrying in seconds
    enqueue_retry_deadline = 20.0
    
    def run(self, **kwargs):
        # Task implementation here
        pass
```

#### How It Works

When a task is enqueued using `asap()`, `later()`, or other methods, the library automatically applies the configured retry policy to the Cloud Tasks API call. If the API call fails with one of the specified exceptions, it will be retried according to the configured policy.

The retry mechanism uses an exponential backoff strategy:
- First retry occurs after `initial` seconds
- Each subsequent retry's delay is multiplied by `multiplier`
- Delay is capped at `maximum` seconds
- Total retry time is limited to `deadline` seconds

**Important**: For a retry policy to be created, `enqueue_retry_exceptions` must be defined - this is the only mandatory configuration. If this setting is `None`, no retry will be performed.

For the other parameters (`initial`, `maximum`, `multiplier`, `deadline`), if no explicit value is set, the default values from Google's Retry object will be used (initial=1.0s, maximum=60.0s, multiplier=2.0, deadline=120.0s).

Recommended values based on Google's retry defaults:
- initial: 1.0 second
- maximum: 60.0 seconds
- multiplier: 2.0
- deadline: 120.0 seconds (listed as timeout in the Google API)

Note that this retry mechanism only applies to the task creation API call. Once a task is successfully created, the Cloud Tasks queue's own retry configuration takes over for task execution failures.

## Periodic Task

Tasks can be executed recurrently, using a crontab syntax.

The backend used in Google Cloud Scheduler.

```python
from django_cloud_tasks.tasks import PeriodicTask


class RecurrentTask(PeriodicTask):
    run_every = "* * 0 0"  # crontab syntax
    
    def run(self):
        # computation goes here
        ...

```

For these tasks to be registered in Cloud Scheduler, you must execute the setup once 
(in production, usually at the same momento you perform database migrations, ou collect static files)

```shell
python manage.py schedule_tasks
```

If you need, you can also run these tasks synchronously or asynchronously, they will behave exactly as a task on demand:

```python
RecurrentTask.asap()  # run async
RecurrentTask.sync()  # run sync
```

## Publisher

Messages can be sent to a Pub/Sub topic, synchronously or asynchronously.

The backend used in Google Cloud PubSub topics.

```python
from django_cloud_tasks.tasks import PublisherTask


class MyPublisher(PublisherTask):
    @classmethod
    def topic_name(cls) -> str:
        return "potato"  # if you don't set one, we'll use the class name (ie. my-publisher)
    

MyPublisher.sync(message={"x": 10, "y": 3})  # publish synchronously
MyPublisher.asap(message={"x": 10, "y": 3})  # publish asynchronously, using Cloud Tasks

```

For convenience, there's also a dynamic publisher specialized in publishing Django models.

```python
from django_cloud_tasks.tasks import ModelPublisherTask
from django.db.models import Model


class MyModelPublisherTask(ModelPublisherTask):
    @classmethod
    def build_message_content(cls, obj: Model, **kwargs) -> dict:
        return {"pk": obj.pk}  # serialize your model

    @classmethod
    def build_message_attributes(cls, obj: Model, **kwargs) -> dict[str, str]:
        return {}  # any metadata you might want to send as attributes
    
    
one_obj = MyModel.objects.first()

MyModelPublisherTask.sync(obj=one_obj) # publish synchronously
MyModelPublisherTask.asap(obj=one_obj) # publish asynchronously, using Cloud Tasks

```

## Subscriber

Messages can be received in a Pub/Sub subscription, synchronously or asynchronously.

The backend used in Google Cloud PubSub subscriptions.

```python
from django_cloud_tasks.tasks import SubscriberTask


class MySubscriber(SubscriberTask):
    def run(self, content: dict, attributes: dict[str, str] | None = None):
        ...  # process the message you received
    
    @classmethod
    def topic_name(cls) -> str:
        return "potato"
    
    @classmethod
    def subscription_name(cls) -> str:
        return "tomato"  # if you don't set it, we'll use the class name (eg. my-subscriber)

```

## Contributing

When contributing to this repository, you can setup:

### As an application (when contributing)

- Install packages:

```
    make dependencies
```


- If you have changed the package dependencies in poetry.lock:

```
    make update
```

### As a package (when inside another application)

- In the application's pyproject.toml, add the remote private repository and the package with version:
```
[packages]
django-google-cloud-tasks = {version="<version>"}
```

- During development, if you wish to install from a local source (in order to test integration with ease):
```
    # inside the application
    poetry add -e /path/to/this/lib
```

## Testing

To run tests:

```shell
make test
```

To fix linter issues:
```shell
make style
```

## Version

Use [Semantic versioning](https://semver.org/).
