class PRReviewAgentError(Exception):
    """
    Base class for all exceptions in this project.
    Every custom exception below inherits from this.
    This lets callers catch all our exceptions with a single except clause
    if they want to, while still being able to catch specific ones.
    """
    pass


## Webhook exceptions

class WebhookValidationError(PRReviewAgentError):
    """
    Raised when a GitHub webhook fails HMAC signature validation.
    This means the request did not come from GitHub, or the secret is wrong.
    The webhook receiver should return HTTP 401 when this is raised.
    """
    pass

class WebhookParseError(PRReviewAgentError):
    """
    Raised when a valid (signature-verified) webhook payload cannot be parsed
    into our expected model. Usually means GitHub changed their payload format
    or we received an event type we do not support.
    The webhook receiver should return HTTP 400 when this is raised.
    """
    pass


## Job queue exceptions

class JobEnqueueError(PRReviewAgentError):
    """
    Raised when a job cannot be placed into the Redis queue.
    Usually means Redis is down or unreachable.
    The webhook receiver should return HTTP 503 when this is raised
    so GitHub knows to retry the webhook delivery.
    """
    pass

class  DuplicateWebhookError(PRReviewAgentError):
    """
    Alias for DuplicateJobError, used in Phase 4 job queue layer.
    Raised by enqueue_review_job() when the idempotency key already exists.
    Includes the idempotency_key so the caller can log which event was skipped.
    Not an error — the caller should return HTTP 200 silently.
    """
    def __init__(self, message: str, idempotency_key: str | None = None):
        super().__init__(message)
        self.idempotency_key = idempotency_key

class DuplicateJobError(PRReviewAgentError):
    """
    Raised when we detect we have already processed this exact webhook event.
    This is the idempotency check - GitHub replays webhooks on timeout.
    Not an error per se - the caller should return HTTP 200 silently.
    """
    pass


# Memory / Storage Exceptions

class MemoryStoreError(PRReviewAgentError):
    """
    Raised when a read or write to any memory store (Redis, Qdrant, Postgres) fails.
    Includes the store name so we know which one is down.
    """
    def __init__(self, message: str, store: str | None = None):
        super().__init__(message)
        self.store = store
