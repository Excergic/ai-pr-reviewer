import json

from backend.core.exceptions import WebhookParseError
from backend.models.enums import PullRequestAction, WebhookEventType
from backend.models.webhook import WebhookEvent

def parse_webhook_payload(
    raw_body: bytes,
    event_type_header: str | None,
) -> WebhookEvent | None:
    """
    Parses a raw GitHub webhook payload into a WebhookEvent model.

    Returns a WebhookEvent if this is an event we should process.
    Returns None if this is an event type we should silently ignore.
    Raises WebhookParseError if the payload is malformed or missing required fields.

    Args:
        raw_body:
            The raw request body as bytes (same bytes we used for HMAC validation).

        event_type_header:
            The value of the X-GitHub-Event header.
            e.g. "pull_request", "push", "star", "fork"
            None if the header was not present.

    Returns:
        WebhookEvent if this is a pull_request event we should process.
        None if this is an event type we should ignore (push, star, fork, etc.)

    Raises:
        WebhookParseError: if the payload cannot be parsed or is missing required fields.

    Example:
        event = parse_webhook_payload(
            raw_body=b'{...}',
            event_type_header="pull_request",
        )
        if event is None:
            return  # silently ignore
        # proceed with event
    """

    # I only care about pull_request event
    if event_type_header != WebhookEventType.PULL_REQUEST:
        return None
    
    try:
        payload_dict = json.loads(raw_body)

    except json.JSONDecodeError as e:
        raise WebhookParseError(
            f"Request body is not valid JSON: {e}"
        ) from e

    # I only trigger a review on: opened, synchronize, reopened.

    action = payload_dict.get("action")
    if action not in {a.value for a in PullRequestAction}:
        return None
    
    try:
        event = WebhookEvent.model_validate(payload_dict)
    except Exception as e:
        raise WebhookParseError(
            f"GitHub webhook payload is missing required fields or has unexpected format. "
            f"Details: {e}"
        ) from e

    return event