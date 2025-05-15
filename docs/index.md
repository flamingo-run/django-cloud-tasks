# Welcome to Django Cloud Tasks!

Django Cloud Tasks is your go-to Django app for effortlessly running asynchronous tasks on Google Cloud Platform. It makes it a breeze to work with Google Cloud Tasks, Cloud Scheduler, and Cloud Pub/Sub right from your Django project.

Think of it as a way to offload heavy work (like image processing or report generation), schedule future jobs (like nightly cleanups), or react to events in a decoupled way (like sending a welcome email when a new user signs up) – all without making your users wait or bogging down your web servers.

This documentation will guide you through setting up and using its powerful features.

## Installation

Getting this bad boy into your project is super easy. Just pip install it:

```bash
pip install django-cloud-tasks
```

## Django Setup

1.  Add `'django_cloud_tasks'` to your `INSTALLED_APPS` in `settings.py`:

    ```python
    INSTALLED_APPS = [
        # ... other apps
        'django_cloud_tasks',
        # ...
    ]
    ```

2.  Include the Django Cloud Tasks URLs in your main `urls.py`. These URLs are the endpoints that Google Cloud services will call to trigger your tasks.

    ```python
    from django.urls import path, include

    urlpatterns = [
        # ... other urls
        path('my-tasks-prefix/', include('django_cloud_tasks.urls')), # You can choose your own prefix
        # ...
    ]
    ```
    Make sure this endpoint is publicly accessible if you're not running in a private VPC, as Google Cloud services need to reach it.

## Required Google Cloud APIs

To use `django-cloud-tasks` effectively, you'll need to enable the following APIs in your Google Cloud Project:

*   [Cloud Tasks API](https://console.cloud.google.com/marketplace/product/google/cloudtasks.googleapis.com)
*   [Cloud Scheduler API](https://console.cloud.google.com/marketplace/product/google/cloudscheduler.googleapis.com)
*   [Pub/Sub API](https://console.cloud.google.com/marketplace/product/google/pubsub.googleapis.com)
*   Optional: [Admin SDK API](https://console.cloud.google.com/marketplace/product/google/admin.googleapis.com) (Needed for some advanced features or if you are working with domain-wide delegation for service accounts, though typically not required for basic task and pub/sub operations with OIDC or standard service account authentication).

## Core Configuration (`settings.py`)

You can tweak how Django Cloud Tasks behaves through your Django `settings.py` file. All settings are prefixed with `DJANGO_CLOUD_TASKS_`. You can also set these as environment variables (which will take precedence if both are set).

Here are some of the main ones to get you started:

*   **`DJANGO_CLOUD_TASKS_ENDPOINT`**: The full base URL of your application (e.g., `https://your-cool-app.com`). This is crucial because Cloud Tasks, Scheduler, and Pub/Sub push subscriptions need to know the exact URL to send HTTP requests to trigger your tasks. It's often your Cloud Run service URL.
    *   Default: `"http://localhost:8080"`
    *   Example: `DJANGO_CLOUD_TASKS_ENDPOINT = "https://myapp.com"`

*   **`DJANGO_CLOUD_TASKS_APP_NAME`**: A unique name for your application or service. This is used to prefix and organize resources in GCP, such as Cloud Scheduler job names or Pub/Sub topic/subscription names, making it easier to manage them, especially if you have multiple applications in the same GCP project.
    *   Default: `None` (reads from `APP_NAME` environment variable if set)
    *   Example: `DJANGO_CLOUD_TASKS_APP_NAME = "user-service"`

*   **`DJANGO_CLOUD_TASKS_EAGER`**: If set to `True`, tasks will run synchronously (i.e., immediately in the same process) instead of being sent to Google Cloud. This is incredibly useful for local development and testing, as it bypasses the need for GCP setup and lets you debug tasks like regular function calls.
    *   Default: `False`
    *   Example: `DJANGO_CLOUD_TASKS_EAGER = settings.DEBUG` (to enable eager mode when Django's `DEBUG` is true)

*   **`DJANGO_CLOUD_TASKS_URL_NAME`**: The specific Django URL *name* (not path) within the included `django_cloud_tasks.urls` that is used as the endpoint for on-demand tasks triggered by Cloud Tasks and scheduled tasks triggered by Cloud Scheduler.
    *   Default: `"tasks-endpoint"`

*   **`DJANGO_CLOUD_TASKS_DELIMITER`**: A string used to join parts of names, for example, when constructing default queue names, scheduler job names, or Pub/Sub topic/subscription names (e.g., `my-app--my-task`).
    *   Default: `"--"`

*   **Header Propagation**: Settings related to header propagation are covered in detail in the "Header Propagation" section.

There are more settings for fine-tuning retries, Pub/Sub behavior, and specific service interactions. We'll touch upon many of these in the relevant sections. For a comprehensive list, you can always refer to the `django_cloud_tasks.apps.DjangoCloudTasksAppConfig` class.

With this foundational setup, you're ready to dive into defining and using the different types of tasks! 