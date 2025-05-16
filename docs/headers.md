# Header Propagation

When you're dealing with asynchronous tasks, especially in a microservices or distributed environment, it's often crucial to carry over some context from the initial request that triggered the task. Header propagation allows you to do just that.

## Why Propagate Headers?

Common use cases include:

*   **Distributed Tracing:** To track a single logical operation as it flows through multiple services or asynchronous tasks. Headers like `traceparent` (as used by OpenTelemetry and others) or `X-Cloud-Trace-Context` (used by Google Cloud) are prime candidates.
*   **Tenant/User Context:** If you have a multi-tenant application, you might want to propagate a `X-Tenant-ID` or `X-User-ID` so the task execution environment knows which tenant's data to operate on or which user initiated the action (primarily for logging or non-security-sensitive context).
*   **Feature Flags or A/B Testing Context:** Propagating headers related to feature flags or A/B testing variants can ensure consistent behavior in asynchronous tasks.
*   **Client Information:** Propagating `User-Agent` or custom client version headers (`X-Client-Version`) for logging and debugging purposes.

## How It Works

Header propagation relies on middleware to manage context:

1.  **Capture:** The `HeadersContextMiddleware` intercepts incoming Django requests, extracts headers specified in `DJANGO_CLOUD_TASKS_PROPAGATED_HEADERS`, and stores them in a request-local context.
2.  **Forwarding:**
    *   **Cloud Tasks (On-Demand/Scheduled):** When a task is pushed, these stored headers are added as HTTP headers to the request Cloud Tasks (or Cloud Scheduler) makes to your application.
    *   **Pub/Sub (PublisherTask):** Propagated headers are embedded as a dictionary within the JSON payload of the Pub/Sub message, under the key defined by `DJANGO_CLOUD_TASKS_PROPAGATED_HEADERS_KEY`.
3.  **Retrieval:**
    *   **Cloud Tasks:** Within your `Task` or `PeriodicTask`, `self._metadata.custom_headers` provides access to these propagated HTTP headers.
    *   **Pub/Sub:** The `PubSubHeadersMiddleware` extracts the embedded headers from the message payload when a push request for a `SubscriberTask` arrives. Your `SubscriberTask` then typically accesses them from the message `content` dictionary.

## Configuration

### 1. Middleware Setup

To enable header propagation, you **must** add the relevant middleware to your `settings.py`:

```python
MIDDLEWARE = [
    # ... other django middleware ...
    'django_cloud_tasks.middleware.HeadersContextMiddleware', # (1)
    'django_cloud_tasks.middleware.PubSubHeadersMiddleware', # (2)
    # ... other app middleware ...
]
```

1. Essential for capturing headers from incoming Django requests and making them available for propagation. Also helps make headers available within a task's execution if they were propagated by Cloud Tasks.
2. Specifically for tasks triggered by Pub/Sub push subscriptions. It extracts headers embedded in the Pub/Sub message body.

*   `HeadersContextMiddleware`: Essential for capturing headers from incoming Django requests and making them available for propagation when new tasks are initiated. It also helps make headers available within a task's execution if they were propagated by Cloud Tasks.
*   `PubSubHeadersMiddleware`: Specifically for tasks triggered by Pub/Sub push subscriptions. It extracts headers that were embedded in the Pub/Sub message body by a `PublisherTask` and loads them into the Django request context for the subscriber task handler.

### 2. Settings for Propagation

You configure which headers are propagated and how they are keyed in Pub/Sub messages via your Django `settings.py`:

*   **`DJANGO_CLOUD_TASKS_PROPAGATED_HEADERS`**: A list of HTTP header names that you want to capture and propagate. The matching from incoming requests is case-insensitive.
    *   Default: `["traceparent"]`
    *   Example:
        ```python
        DJANGO_CLOUD_TASKS_PROPAGATED_HEADERS = [
            "traceparent",
            "X-Request-ID",
            "X-Tenant-ID",
            "X-User-ID",
            "Accept-Language",
        ]
        ```

*   **`DJANGO_CLOUD_TASKS_PROPAGATED_HEADERS_KEY`** (For Pub/Sub `PublisherTask` / `SubscriberTask`):
    This setting defines the key within the JSON message body where the dictionary of propagated headers will be stored by `PublisherTask` and read from by `PubSubHeadersMiddleware` (and your `SubscriberTask`).
    *   Default: `"_http_headers"`
    *   Example:
        ```python
        DJANGO_CLOUD_TASKS_PROPAGATED_HEADERS_KEY = "_propagated_context_headers"
        ```

## Accessing Propagated Headers

### Tasks

These tasks are executed via an HTTP request from Google Cloud Tasks/Scheduler. Propagated headers are part of this request.

Access them via `self._metadata.custom_headers` in your task's `run` method. This dictionary holds headers from the task execution request that were listed in `DJANGO_CLOUD_TASKS_PROPAGATED_HEADERS`.

```python
from django_cloud_tasks.tasks import Task


class ProcessDataWithTraceTask(Task):
    def run(self, data_id: int):
        trace_id = self._metadata.custom_headers.get("traceparent") # (1)
        tenant_id = self._metadata.custom_headers.get("x-tenant-id")

        print(f"Executing for data ID: {data_id}, Trace: {trace_id}, Tenant: {tenant_id}")
        # ... your task logic ...
```

1. Headers in `custom_headers` are typically lowercased by the web server/Django.

### Pub/Sub

With `PublisherTask`, headers are embedded in the Pub/Sub message *body*. Your `SubscriberTask` accesses them from the `content` dictionary using the `DJANGO_CLOUD_TASKS_PROPAGATED_HEADERS_KEY`.

```python
from django_cloud_tasks.tasks import SubscriberTask
from django_cloud_tasks.tasks.helpers import get_app # (1)

class AuditLogSubscriber(SubscriberTask):
    @classmethod
    def topic_name(cls) -> str:
        return "user-activity-events"

    def run(self, content: dict, attributes: dict[str, str] | None = None):
        headers_key = get_app().propagated_headers_key # (2)
        propagated_headers = content.get(headers_key, {}) # (3)

        user_id = propagated_headers.get("X-User-ID") # (4)
        request_id = propagated_headers.get("X-Request-ID")

        print(f"Audit event: {content}, User: {user_id}, Request: {request_id}")
        # ... audit logging ...
```

1. Helper to get the app config, useful for accessing settings like `propagated_headers_key` dynamically.
2. Get the configured key for propagated headers.
3. Safely retrieve the dictionary of propagated headers from the message content.
4. Access specific headers. The case here matches how they were put into the dictionary by `PublisherTask`.

By correctly setting up the middleware and configurations, header propagation provides valuable context for your asynchronous operations.