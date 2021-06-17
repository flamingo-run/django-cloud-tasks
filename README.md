![Github CI](https://github.com/flamingo-run/django-cloud-tasks/workflows/Github%20CI/badge.svg)
[![Maintainability](https://api.codeclimate.com/v1/badges/4e211a8dc7a2520873c6/maintainability)](https://codeclimate.com/github/flamingo-run/django-cloud-tasks/maintainability)
[![Test Coverage](https://api.codeclimate.com/v1/badges/4e211a8dc7a2520873c6/test_coverage)](https://codeclimate.com/github/flamingo-run/django-cloud-tasks/test_coverage)
[![python](https://img.shields.io/badge/python-3.8-blue.svg)]()

# Django Cloud Tasks

Powered by [GCP Pilot](https://github.com/flamingo-run/gcp-pilot).

## APIs

The following APIs must be enabled in your project(s):

- [Cloud Tasks API](https://console.cloud.google.com/marketplace/product/google/cloudtasks.googleapis.com)
- [Cloud Scheduler API](https://console.cloud.google.com/marketplace/product/google/cloudscheduler.googleapis.com)
- [Admin SDK API](https://console.cloud.google.com/marketplace/product/google/admin.googleapis.com)

## How it works

> Add ``GOOGLE_CLOUD_TASKS_ENDPOINT`` to your Django settings or as an environment variable

![image](https://user-images.githubusercontent.com/9717144/100749131-00cce780-33c3-11eb-8f2a-b465bc0a45bb.png)

## Setup

### As an application (when contributing)

- Install packages:

```
    make dependencies
```


- If you have changed the package dependencies in Pipfile:

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
    poetry run pip install /<path>/<to>/<django-cloud-tasks>
```

## Usage

See task examples here: [sample_project/sample_app/tasks.py]. Create them in `[app]/tasks.py`.

Add to the app configs:

```
class MyAppConfig(AppConfig):
    name = 'my_app'
    
    def ready(self):
        from slackbot import tasks  # pylint: disable=import-outside-toplevel,unused-import 
```


Add to your `urls.py`:

```
    path('__my_tasks/', include('django_cloud_tasks.urls')),
```


Set in your settings:

```

INSTALLED_APPS = [
    # ...
    'django_cloud_tasks',
    # ...
]

GOOGLE_CLOUD_TASKS_ENDPOINT = 'https://your-domain/'
GOOGLE_CLOUD_TASKS_APP_NAME = 'some-app-name'
```

When you've specified the tasks, run to recreate your schedules and subscriptions:

```
python manage.py initialize_tasks
```

(If you get an error: enable the APIs it wants + go to [Your AppEngine settings](https://console.cloud.google.com/appengine/start) and create a "Location" somewhere you like).

To call the tasks:

```
MyTask().delay(**kwargs) # call it through a queue
MyTask().later(when=time_in_seconds or timedelta or datetime) # call it later
```

## Tests

To run tests:

```
make test
```


## Version

Use [Semantic versioning](https://semver.org/).
