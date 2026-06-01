from enum import Enum

class PullRequestAction(str, Enum):
    """
    Actions on a pull_request event that trigger a review.
    We ignore: closed, labeled, assigned, etc.
    """
    OPENED = "opened"
    SYNCHRONIZE = "synchronize"
    REOPENED = "reopened"

class WebhookEventType(str, Enum):
    """
    GitHub webhook event types we handle.
    We ignore all other event types silently.
    """
    PULL_REQUEST = "pull_request"

