# Publishing & Subscribing (Google Cloud Pub/Sub)

Django Cloud Tasks seamlessly integrates with Google Cloud Pub/Sub, enabling you to build powerful event-driven architectures. You can publish messages to Pub/Sub topics when something interesting happens in your application, and define subscriber tasks that react to these messages asynchronously.

## Publishing Messages

Messages are published to specific "topics." You can think of a topic as a named channel for a certain category of events (e.g., "user-signups", "order-updates").

There are two main base classes for creating publishers:

1.  **`PublisherTask`**: For publishing general-purpose dictionary-based messages.
2.  **`ModelPublisherTask`**: A specialized helper for easily publishing messages related to Django model instance events (e.g., when a model is created, updated, or deleted).

### 1. Basic Publisher: `PublisherTask`

Inherit from `PublisherTask` to define a generic message publisher. The primary method to override is `topic_name()`.

**Example: Publishing User Action Events**

Let's say we want to publish an event whenever a critical user action occurs, like a password change or profile update.

```python
# In your app's tasks.py or a dedicated publishers.py file

from django_cloud_tasks.tasks import PublisherTask

class UserActionEventPublisher(PublisherTask):
    @classmethod
    def topic_name(cls) -> str:
        # This will be the base name for your topic.
        # The final name in GCP might be prefixed (see "Topic Naming" below).
        return "user-actions"

# --- How to use it ---
# In your views.py, after a user successfully changes their password:
# user = request.user
# event_payload = {
#     "user_id": user.id,
#     "action_type": "password_changed",
#     "ip_address": get_client_ip(request), # A helper function to get IP
#     "timestamp": timezone.now().isoformat()
# }
# UserActionEventPublisher.asap(message=event_payload, attributes={"priority": "high"})

# Or publish synchronously (e.g., for tests or if DJANGO_CLOUD_TASKS_EAGER = True):
# UserActionEventPublisher.sync(message=event_payload, attributes={"source": "test_suite"})
```

**How to run `PublisherTask`:**
*   `YourPublisher.asap(message: dict, attributes: dict[str, str] | None = None)`: Enqueues the publishing action itself as an on-demand task (via Cloud Tasks) to publish the message to Pub/Sub. This makes the HTTP request that publishes the message asynchronous.
*   `YourPublisher.sync(message: dict, attributes: dict[str, str] | None = None)`: Directly publishes the message to Pub/Sub in the current process.

### 2. Model-Specific Publisher: `ModelPublisherTask`

This class is incredibly useful when the event you want to publish is directly tied to a Django model instance (e.g., an `Order` was created, an `Article` was updated).

**Example: Publishing Order Creation Events**

```python
# In your app's tasks.py or publishers.py
# Assuming you have an Order model: models.py
# class Order(models.Model):
#     order_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
#     user = models.ForeignKey(User, on_delete=models.CASCADE)
#     total_amount = models.DecimalField(max_digits=10, decimal_places=2)
#     status = models.CharField(max_length=50, default="pending")
#     created_at = models.DateTimeField(auto_now_add=True)

from django.db import models # Your Django models
from django_cloud_tasks.tasks import ModelPublisherTask

class OrderCreatedEvent(ModelPublisherTask):
    @classmethod
    def build_message_content(cls, obj: models.Model, **kwargs) -> dict:
        # obj is an instance of your Django model (e.g., an Order instance)
        # kwargs can receive any extra arguments passed to asap(), sync(), etc.
        order = obj # Explicitly cast/type hint if needed
        return {
            "order_id": str(order.order_id),
            "user_id": order.user_id,
            "total_amount": float(order.total_amount), # Pub/Sub prefers basic JSON types
            "status": order.status,
            "created_at_iso": order.created_at.isoformat(),
            "campaign_source": kwargs.get("campaign_source") # Example of using an extra kwarg
        }

    @classmethod
    def build_message_attributes(cls, obj: models.Model, **kwargs) -> dict[str, str]:
        order = obj
        return {
            "event_type": "order_created",
            "customer_segment": "retail", # Example attribute
            "region": kwargs.get("region", "unknown")
        }

    # topic_name() by default uses the model's app_label and model_name (e.g., "myapp-order")
    # You can override it if needed (see "Customizing Publishers" below).

# --- How to use it ---
# After an order instance is created and saved:
# new_order = Order.objects.create(user=request.user, total_amount=cart.total, ...)

# Publish ASAP:
# OrderCreatedEvent.asap(obj=new_order, campaign_source="spring_sale", region="emea")

# Or, to ensure the message is sent ONLY if the current database transaction commits successfully:
# from django.db import transaction
# with transaction.atomic():
#     new_order.save() # Or new_order.objects.create(...)
#     OrderCreatedEvent.sync_on_commit(obj=new_order, campaign_source="newsletter")
```

**Key methods for `ModelPublisherTask`:**

*   **`build_message_content(cls, obj: Model, **kwargs) -> dict` (Required):** You implement this to transform your model instance (`obj`) and any extra `kwargs` into the main JSON payload of the Pub/Sub message.
*   **`build_message_attributes(cls, obj: Model, **kwargs) -> dict[str, str]` (Required):** You implement this to create a dictionary of string-to-string attributes for the Pub/Sub message. Attributes are useful for filtering messages on the subscriber side without needing to parse the full JSON payload.
*   `sync_on_commit(obj: Model, **kwargs)`: A very handy method that delays the actual publishing until the current database transaction is successfully committed. This prevents sending messages for data that might be rolled back.

### Topic Naming Convention

*   **Default `topic_name()` for `PublisherTask`:** Uses the class name (e.g., `UserActionEventPublisher` becomes topic base name `UserActionEventPublisher`).
*   **Default `topic_name()` for `ModelPublisherTask`:** Uses `app_label-model_name` (e.g., if `Order` is in `sales` app, it becomes `sales-order`).
*   **Global Prefixing:** If `DJANGO_CLOUD_TASKS_APP_NAME` is set in your Django settings (e.g., to `"my-ecom-service"`), this name, along with the `DJANGO_CLOUD_TASKS_DELIMITER` (default `"--"`), will be **prepended** to the base topic name. So, `UserActionEventPublisher` could become `my-ecom-service--UserActionEventPublisher` in GCP.
*   This prefixing helps organize topics in GCP, especially if multiple services share a project.

### Ensuring Topics Exist (`set_up`)

`PublisherTask` (and by extension `ModelPublisherTask`) has a `set_up()` class method. Calling `YourPublisherTask.set_up()` will attempt to create the Pub/Sub topic in GCP if it doesn't already exist.

```python
# You might call this in an AppConfig.ready() or a custom management command
# UserActionEventPublisher.set_up()
# OrderCreatedEvent.set_up() # For ModelPublisherTask, it uses the default topic name based on model
```
This does *not* set up IAM permissions for publishing; your service account running the Django app needs `pubsub.topics.publish` permission on the topic or project.

## Subscribing to Messages (`SubscriberTask`)

To process messages published to a topic, you define a `SubscriberTask`. This task will be triggered via an HTTP push request from Google Cloud Pub/Sub to a dedicated endpoint in your Django application when a new message arrives on the subscribed topic.

**Example: Processing User Action Events and Order Notifications**

```python
# In your app's tasks.py (or a dedicated subscribers.py file)

from django_cloud_tasks.tasks import SubscriberTask
# from myapp.services import fraud_detection_service, notification_service

class UserActionAuditor(SubscriberTask):
    @classmethod
    def topic_name(cls) -> str:
        # This MUST match the topic name used by UserActionEventPublisher
        return "user-actions"

    # The run method receives the deserialized message content and attributes
    def run(self, content: dict, attributes: dict[str, str] | None = None):
        print(f"Auditing user action: {content.get('action_type')} for user {content.get('user_id')}")
        print(f"  Attributes: {attributes}")
        # if content.get('action_type') == 'password_changed':
        #     fraud_detection_service.check_suspicious_login_after_password_change(content)
        return {"status": "action_audited", "user_id": content.get('user_id')}

class OrderNotificationHandler(SubscriberTask):
    @classmethod
    def topic_name(cls) -> str:
        # This MUST match the topic from OrderCreatedEvent. For an Order model in 'sales' app:
        return "sales-order" # Or your custom topic name if overridden in ModelPublisherTask

    def run(self, content: dict, attributes: dict[str, str] | None = None):
        print(f"New order received for processing: {content.get('order_id')}")
        print(f"  Event Type (from attribute): {attributes.get('event_type')}")
        # notification_service.send_order_confirmation_email(content.get('user_id'), content)
        # inventory_service.reserve_stock(content.get('order_id'), ...)
        return {"status": "order_processed", "order_id": content.get('order_id')}
```

**Key elements for `SubscriberTask`:**

*   **`topic_name(cls) -> str` (Required):** Specifies which Pub/Sub topic this task subscribes to. This name needs to match the *base name* of the publisher's topic (before any global `APP_NAME` prefixing).
*   **`run(content: dict, attributes: dict[str, str] | None = None)`:** Your core logic to handle the incoming message. `content` is the deserialized JSON payload, and `attributes` are the string key-value pairs sent with the Pub/Sub message.

### Subscription Naming Convention

*   **Default `subscription_name()`:** Similar to topics, the subscription name is derived from `DJANGO_CLOUD_TASKS_APP_NAME` (if set), the `DJANGO_CLOUD_TASKS_DELIMITER`, and the `SubscriberTask` class name (e.g., `my-ecom-service--UserActionAuditor`).
*   This name is used for the actual Pub/Sub Subscription resource created in GCP.

### Setting Up and Deploying Subscriptions

Defining the `SubscriberTask` class in Python doesn't automatically create the subscription in Google Cloud Pub/Sub. You need to run a management command:

```bash
python manage.py initialize_subscribers
```

**What this command does:**

1.  Scans your project for all `SubscriberTask` classes.
2.  For each task, it calls its `set_up()` class method.
3.  The default `set_up()` method in `SubscriberTask` will:
    *   Attempt to create a Pub/Sub **topic** (using the subscriber's `topic_name()`) if it doesn't already exist. This is a safety measure; ideally, publishers manage their topics.
    *   Create or update a Pub/Sub **subscription** (using `subscription_name()`) to that topic.
    *   Configure the subscription to PUSH messages via HTTP to a Django endpoint specific to that `SubscriberTask` (derived from `subscription_url()`).
    *   Enable OIDC authentication by default for these push requests (see `_use_oidc_auth` customization).
    *   Apply other subscription settings like retry policies, dead-letter topics, and filters if customized on the task class.

The command will output `[+]`, `[~]`, `[-]` for added, updated, or (less commonly) deleted subscriptions.

**When to run `initialize_subscribers`?**
Run this as part of your deployment process, especially when you add new `SubscriberTask`s or change their subscription configurations (like `topic_name`, `filter`, retry policies, etc.).

## Customizing Publishers

### Custom Topic Names for Publishers

For both `PublisherTask` and `ModelPublisherTask`, you can override `topic_name(cls, ...)` for more control.

```python
class LegacySystemEventPublisher(PublisherTask):
    @classmethod
    def topic_name(cls) -> str:
        # Overrides the default naming based on class name
        return "legacy-integration-bus"

# For ModelPublisherTask, topic_name can also use the object
class ProductUpdateToSpecificChannel(ModelPublisherTask):
    @classmethod
    def topic_name(cls, obj: models.Model, **kwargs) -> str:
        product = obj
        # Example: route product updates to different topics based on category
        if product.category == "electronics":
            return "product-updates-electronics"
        return "product-updates-general"
    # ... build_message_content and build_message_attributes ...
```
Remember that if `DJANGO_CLOUD_TASKS_APP_NAME` is set, it will still be prefixed unless your override includes it or is absolute.

## Customizing Subscribers

`SubscriberTask` offers several attributes and methods for fine-tuning the GCP Pub/Sub subscription.

### Custom Subscription Name (`subscription_name`)

While default naming is usually fine, you can override `subscription_name()` if needed, similar to `schedule_name` for periodic tasks.

### Custom Subscription URL (`subscription_url`)

This is rarely needed, as the default URL points to the correct handler in `django-cloud-tasks`. Overriding this means you're pointing Pub/Sub to a custom endpoint you've built.

### OIDC Authentication for Push Endpoint (`_use_oidc_auth`)

*   Class attribute `_use_oidc_auth: bool = True`.
*   Controls if the Pub/Sub push subscription expects Google to send an OIDC token for authentication. Generally, keep this `True` if your Django app runs on a service like Cloud Run that can validate these tokens.

### Subscription Retry Policy (Message Acknowledgement Deadline & Backoff)

These settings on your `SubscriberTask` class map to the Pub/Sub subscription's message delivery retry configuration. They define how Pub/Sub handles messages if your endpoint doesn't acknowledge them (e.g., returns an error or times out).

*   **`max_retries: int | None = UNSET`**: Maximum delivery attempts before sending to a dead-letter topic (if configured). Defaults to global `DJANGO_CLOUD_TASKS_SUBSCRIBER_MAX_RETRIES` or GCP default.
*   **`min_backoff: int | None = UNSET`**: Minimum delay (in seconds) Pub/Sub waits before redelivering an unacknowledged message. Defaults to global `DJANGO_CLOUD_TASKS_SUBSCRIBER_MIN_BACKOFF` or GCP default (typically 10s).
*   **`max_backoff: int | None = UNSET`**: Maximum delay (in seconds) for redelivery. Defaults to global `DJANGO_CLOUD_TASKS_SUBSCRIBER_MAX_BACKOFF` or GCP default (typically 600s).

```python
class TimeSensitiveAlertSubscriber(SubscriberTask):
    topic_name = "critical-alerts"
    min_backoff = 5    # Retry quickly for these alerts, minimum 5 seconds
    max_backoff = 60   # But don't wait too long, max 1 minute
    max_retries = 3    # Only try 3 times before considering it failed (e.g., for dead-lettering)

    def run(self, content: dict, attributes: dict[str, str] | None = None):
        print(f"Processing time-sensitive alert: {content}")
        # ... alert processing ...
```

### Dead Letter Topics (DLT/DLQ)

If a message consistently fails processing after configured retries, Pub/Sub can forward it to a Dead Letter Topic (DLT), effectively a Dead Letter Queue (DLQ).

*   **`dead_letter_topic_name(cls) -> str | None`**: Override to return the *base name* of the DLT. If `None` (default), no DLT is used for this subscriber.
*   **`dead_letter_subscription_name(cls) -> str`**: Name for the subscription to the DLT (often just the DLT name).

The `initialize_subscribers` command will attempt to set up the DLT and necessary permissions if you configure this. You'll need a separate process or subscriber to monitor and handle messages in the DLT.

```python
class PaymentProcessingSubscriber(SubscriberTask):
    topic_name = "payment-requests"
    max_retries = 5 # After 5 failed attempts, send to DLT

    @classmethod
    def dead_letter_topic_name(cls) -> str | None:
        return "payment-requests-failed" # Base name for the DLT

    def run(self, content: dict, attributes: dict[str, str] | None = None):
        # ... process payment ...
        # if permanent_failure_condition(content):
        #     raise DiscardTaskException() # To prevent retries and avoid DLT for known bad messages
        pass
```

### Message Filtering (`subscription_filter`)

Pub/Sub allows subscriptions to specify a filter, so the subscription only receives messages whose attributes match the filter. This can reduce the number of messages your subscriber task needs to process.

*   **`subscription_filter(cls) -> str | None`**: Return a filter string based on [Pub/Sub filter syntax](https://cloud.google.com/pubsub/docs/subscription-message-filter#filtering_syntax).

```python
class HighPriorityOrderSubscriber(SubscriberTask):
    topic_name = "sales-order" # Subscribes to the same topic as OrderNotificationHandler

    @classmethod
    def subscription_filter(cls) -> str | None:
        # Only receive messages where the 'priority' attribute is 'high'
        return 'attributes.priority = "high"'

    def run(self, content: dict, attributes: dict[str, str] | None = None):
        print(f"Processing HIGH PRIORITY order: {content.get('order_id')}")
        # ... specialized high-priority handling ...
```

### Custom Message Parsing (`message_parser`)

*   **`message_parser(cls) -> Callable`**: A callable used to parse the raw message body received from Pub/Sub. Defaults to `json.loads`.
*   You'd only override this if your publishers are sending non-JSON messages (e.g., raw text, protobuf), which is less common when using this library's `PublisherTask` which serializes to JSON.

This event-driven model using Pub/Sub provides a robust and scalable way to build decoupled applications where services can communicate and react to events without direct dependencies. 