# Scheduled Tasks (Powered by Google Cloud Scheduler)

Scheduled tasks, often known as "cron jobs," are tasks that run automatically on a repeating schedule (e.g., every hour, once a day at 2 AM, every Monday morning). Django Cloud Tasks leverages Google Cloud Scheduler to manage and execute these periodic jobs. Your Django application defines what needs to run, and Cloud Scheduler takes care of triggering it at the right time via an HTTP request.

## Defining a Scheduled Task

You define a scheduled task by inheriting from `django_cloud_tasks.tasks.PeriodicTask`. The most crucial part is setting the `run_every` class attribute to a cron expression that defines the schedule.

**Example: Daily Digest and Hourly Cleanup**

```python
# In your app's tasks.py (e.g., reports/tasks.py or core/tasks.py)

from django_cloud_tasks.tasks import PeriodicTask
from django.utils import timezone
# from myapp.models import UserActivity, TemporaryFile

class GenerateDailyUserActivityDigest(PeriodicTask):
    # Cron expression: "At 00:00 on every day-of-week from Monday through Friday."
    # (Assumes server/Cloud Scheduler timezone is UTC by default)
    run_every = "0 0 * * 1-5"

    def run(self, **kwargs): # kwargs will receive payload from Cloud Scheduler if any is set
        print(f"Generating daily user activity digest for {timezone.now().date()}...")
        # yesterday = timezone.now().date() - timezone.timedelta(days=1)
        # activities = UserActivity.objects.filter(timestamp__date=yesterday)
        # generate_report(activities)
        # send_report_to_admins()
        return {"status": "digest_generated", "date": str(timezone.now().date())}

class HourlyTemporaryFileCleanup(PeriodicTask):
    run_every = "@hourly"  # Cloud Scheduler shorthand for "0 * * * *"

    def run(self, older_than_hours: int = 2, **kwargs):
        print(f"Cleaning up temporary files older than {older_than_hours} hours...")
        # cutoff_time = timezone.now() - timezone.timedelta(hours=older_than_hours)
        # TemporaryFile.objects.filter(created_at__lt=cutoff_time).delete()
        return {"status": "cleanup_done", "older_than_hours": older_than_hours}
```

**Key Attributes for `PeriodicTask`:**

*   **`run_every: str` (Required):** Defines the schedule using the standard [cron format](https://cloud.google.com/scheduler/docs/configuring/cron-job-schedules). Cloud Scheduler also supports shorthands like `@daily`, `@hourly`, `@weekly`, `@monthly`, `@yearly`.
*   **`run(**kwargs)`:** The method containing your task's logic. It's the same as for on-demand tasks. Any JSON payload you define in Cloud Scheduler (or through customization hooks) will be passed as `kwargs`.

## Deploying Scheduled Tasks

Defining the Python class is just the first step. You need to inform Google Cloud Scheduler about your tasks. This is done using a Django management command:

```bash
python manage.py schedule_tasks
```

**What this command does:**

1.  It scans your Django project for all classes inheriting from `PeriodicTask` (ensure these modules are imported by Django at startup).
2.  It compares these definitions against the jobs currently configured in Google Cloud Scheduler for your `DJANGO_CLOUD_TASKS_APP_NAME`.
3.  It then synchronizes the state:
    *   **`[+] Added`**: New jobs are created in Cloud Scheduler for tasks found in your code but not yet scheduled.
    *   **`[~] Updated`**: Existing jobs in Cloud Scheduler are updated if their definition (e.g., cron schedule `run_every`, target URL, payload) has changed in your code.
    *   **`[-] Deleted`**: Jobs in Cloud Scheduler are deleted if their corresponding `PeriodicTask` class has been removed from your code.

**When to run `schedule_tasks`?**

You should run this command as part of your deployment process, any time you add, remove, or modify the definition (especially `run_every` or other schedule-related overrides) of a `PeriodicTask`.

## Customizing Scheduled Task Behavior

You can override several class methods on your `PeriodicTask` subclass to fine-tune how it interacts with Google Cloud Scheduler.

### Custom Job Naming (`schedule_name`)

By default, the Cloud Scheduler job name is constructed using your `DJANGO_CLOUD_TASKS_APP_NAME`, the `DJANGO_CLOUD_TASKS_DELIMITER`, and the task's class name (e.g., `my-app--GenerateDailyUserActivityDigest`). You can customize this for better organization or to adhere to specific naming conventions.

```python
class MonthlyBillingRun(PeriodicTask):
    run_every = "0 3 1 * *" # At 03:00 on day-of-month 1.

    @classmethod
    def schedule_name(cls) -> str:
        # Example: "billing-service-MonthlyBillingRun-prod"
        app_name = get_config("app_name") # Fetches DJANGO_CLOUD_TASKS_APP_NAME
        env = "prod" if not settings.DEBUG else "dev"
        return f"{app_name}-{cls.name()}-{env}" # cls.name() is the class name

    def run(self, **kwargs):
        print("Starting monthly billing run...")
        # ... billing logic ...
```

### Custom HTTP Headers for Scheduler Requests (`schedule_headers`)

You can inject custom HTTP headers into the requests that Cloud Scheduler makes to your task endpoint. This can be useful for passing specific tokens, versioning information, or routing hints that your Django application or infrastructure might use.

```python
class DataSyncWithExternalService(PeriodicTask):
    run_every = "0 */6 * * *" # Every 6 hours

    @classmethod
    def schedule_headers(cls) -> dict:
        # This token might be used by your endpoint's authentication/authorization layer
        return {"X-Scheduler-Auth-Token": "my-secret-scheduler-token", "X-Job-Type": cls.name()}

    def run(self, **kwargs):
        # Your Django view or middleware can inspect request.META for these headers
        # e.g., request.META.get('HTTP_X_SCHEDULER_AUTH_TOKEN')
        print("Running data sync, triggered with custom headers.")
```

### OIDC Authentication for Scheduler Requests (`schedule_use_oidc`)

Determines if OIDC (OpenID Connect) authentication should be used for the HTTP request from Cloud Scheduler to your application. This is the recommended secure way for Google services to call your services.

*   Default: `True`.
*   If `True`, Cloud Scheduler will send a Google-signed OIDC token in the `Authorization` header. Your application endpoint (usually a Cloud Run service or similar) should be configured to validate this token.
*   If `False`, no OIDC token is sent by Scheduler. You would rely on other means of securing your endpoint (e.g., network controls, custom `schedule_headers` with a pre-shared key, though OIDC is preferred).

```python
class PublicDataFetcherTask(PeriodicTask):
    run_every = "@daily"

    @classmethod
    def schedule_use_oidc(cls) -> bool:
        # If this task calls a public, non-OIDC protected part of your app, or if auth is handled differently
        return False # Set to True if your endpoint expects a Google OIDC token

    def run(self, **kwargs):
        print("Fetching public data...")
```

### Scheduler-Level Retry Configuration (`schedule_retries`)

Specifies the number of times Google Cloud Scheduler should retry invoking your task endpoint if the HTTP request fails (e.g., your endpoint returns a 5xx error or doesn't respond).

*   Default: `0` (no retries at the Cloud Scheduler level).
*   This is distinct from any retry logic within your task's `run()` method or Cloud Tasks queue retries (if the scheduled job itself pushes to a Cloud Tasks queue).

```python
class OccasionallyFailingExternalCheck(PeriodicTask):
    run_every = "*/30 * * * *" # Every 30 minutes

    @classmethod
    def schedule_retries(cls) -> int:
        # If the endpoint is down, ask Cloud Scheduler to retry up to 3 times
        return 3

    def run(self, **kwargs):
        print("Performing an external check that might sometimes fail...")
        # ... call external service ...
```

### Custom Payload for Scheduled Tasks

While `PeriodicTask.schedule()` itself takes `**kwargs` which are serialized into the payload for Cloud Scheduler, you typically set these arguments directly in the `run` method's signature with defaults if they are static for the schedule. If you need to dynamically build a more complex payload during the `schedule_tasks` command or want to override what arguments are sent, you would need to customize the `schedule` method itself or ensure your `run` method pulls configuration dynamically.

The default arguments sent in the payload by `schedule()` are simply the `**kwargs` passed to it. If no `kwargs` are passed (common for periodic tasks where the logic is self-contained or configured via `settings`), the payload will be an empty JSON object `{}`.

## How It Works Under the Hood

When `PeriodicTask.schedule()` is invoked (typically by the `schedule_tasks` management command), it communicates with Google Cloud Scheduler to create or update a job. This job is configured to:

1.  Trigger based on the `run_every` cron schedule.
2.  Make an HTTP POST request to the URL generated by `YourTaskClass.url()` (this defaults to the standard task execution endpoint in `django_cloud_tasks.urls`).
3.  Include a JSON payload (by default, an empty dictionary `{}` unless `kwargs` were passed to `schedule` or the task sends a default payload).
4.  Use OIDC authentication and custom headers as configured.

Essentially, Cloud Scheduler acts as a timed trigger that invokes your `PeriodicTask` as if it were an on-demand task call arriving at your application's endpoint.

**Eager Mode Behavior (`DJANGO_CLOUD_TASKS_EAGER = True`)**
If `DJANGO_CLOUD_TASKS_EAGER` is true, running `python manage.py schedule_tasks` will *not* actually interact with Google Cloud Scheduler. Instead, for any tasks that *would have been* added or updated, their `run()` method will be executed synchronously, locally, one time. This is primarily for testing the task logic itself, not the scheduling mechanism.

And that's the rundown on keeping your tasks running like clockwork with scheduled tasks! 