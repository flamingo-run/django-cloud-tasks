![PyPI - Downloads](https://img.shields.io/pypi/dm/django-google-cloud-tasks)

![Github CI](https://github.com/flamingo-run/django-cloud-tasks/workflows/Github%20CI/badge.svg)
[![Maintainability](https://qlty.sh/badges/4c0e2685-e6a9-4dbe-b23d-15f666a98d1d/maintainability.svg)](https://qlty.sh/gh/flamingo-run/projects/django-cloud-tasks)
[![Code Coverage](https://qlty.sh/badges/4c0e2685-e6a9-4dbe-b23d-15f666a98d1d/test_coverage.svg)](https://qlty.sh/gh/flamingo-run/projects/django-cloud-tasks)

[![python](https://img.shields.io/badge/python-3.11-blue.svg)]()
[![python](https://img.shields.io/badge/python-3.12-blue.svg)]()
[![python](https://img.shields.io/badge/python-3.13-blue.svg)]()

# Django Cloud Tasks

**Your go-to Django app for effortlessly running asynchronous tasks on Google Cloud Platform.**

`django-cloud-tasks` makes it a breeze to integrate your Django project with Google Cloud Tasks, Cloud Scheduler, and Cloud Pub/Sub for offloading heavy work, scheduling future jobs, and reacting to events in a decoupled way.

**➡️ For comprehensive documentation, please visit: [django-cloud-tasks.flamingo.codes](https://django-cloud-tasks.flamingo.codes)**

Powered by [GCP Pilot](https://github.com/flamingo-run/gcp-pilot).

## Quick Start

### Installation

```bash
pip install django-google-cloud-tasks
```

### Django Setup

1.  Add `'django_cloud_tasks'` to your `INSTALLED_APPS` in `settings.py`:

    ```python
    INSTALLED_APPS = [
        # ... other apps
        'django_cloud_tasks',
        # ...
    ]
    ```

2.  Include the Django Cloud Tasks URLs in your main `urls.py`:

    ```python
    from django.urls import path, include

    urlpatterns = [
        # ... other urls
        # You can choose your own prefix
        path('my-tasks-prefix/', include('django_cloud_tasks.urls')),
        # ...
    ]
    ```
    Ensure this endpoint is publicly accessible if Google Cloud services need to reach it directly.

## Documentation

For detailed information on configuration, defining tasks (on-demand, scheduled, pub/sub), advanced features, and more, please see our full documentation site:

**[https://django-cloud-tasks.flamingo.codes](https://django-cloud-tasks.flamingo.codes)**

## Contributing

Contributions are welcome! Please refer to the issues section and feel free to submit pull requests.

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details.
