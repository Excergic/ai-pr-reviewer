import hmac
import hashlib

from backend.core.exceptions import WebhookValidationError

def validate_github_signature(
    payload_bytes: bytes, #not in json format because json might be malformed
    signature_header: str | None,
    secret: str
) -> None:
    """
    Validates the HMAC-SHA256 signature on a GitHub webhook request.

    This function either returns None (validation passed) or raises
    WebhookValidationError (validation failed). The caller returns 401 on failure.

    Args:
        payload_bytes:
            The raw request body as bytes, exactly as received from GitHub.
            IMPORTANT: must be the raw bytes before any JSON parsing.
            Parsing changes whitespace and key ordering, which changes the HMAC.

        signature_header:
            The value of the X-Hub-Signature-256 header sent by GitHub.
            Format: "sha256=<64 hex characters>"
            None if the header was not present in the request.

        secret:
            Our webhook secret string (from settings.github_webhook_secret).
            Must match the secret configured in the GitHub webhook settings.

    Raises:
        WebhookValidationError: if signature is missing, malformed, or does not match.

    Example:
        validate_github_signature(
            payload_bytes=b'{"action": "opened", ...}',
            signature_header="sha256=abc123...",
            secret="my-webhook-secret",
        )
        # Returns None if valid, raises WebhookValidationError if not
    """

    if not signature_header:
        raise WebhookValidationError(
            "Missing X-Hub-Signature-256 header. "
            "Request did not come from GitHub or secret is not configured."
        )

    if not signature_header.startswith("sha256="):
        raise WebhookValidationError(
            f"Malformed signature header: '{signature_header}'. "
            "Expected format: 'sha256=<hex_digest>'"
        )

    received_signature = signature_header[len("sha256="):] # extract the signature from the header (7: total length of the header - 1)

    expected_signature = hmac.new(
        key=secret.encode("utf-8"), # convert the secret to bytes
        msg=payload_bytes, 
        digestmod=hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_signature, received_signature):
        raise WebhookValidationError(
            "Signature mismatch. The request body or webhook secret is incorrect. "
            "Verify that GITHUB_WEBHOOK_SECRET matches the secret in GitHub webhook settings."
        )


## this function return None on successfull validation and raise WebhookValidationError on failure