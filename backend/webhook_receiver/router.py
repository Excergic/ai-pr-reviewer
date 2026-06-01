# this is an entry point of all github events

import logging
from fastapi import APIRouter, Depends, HTTPException, Header, Request, status
from fastapi.responses import JSONResponse

from backend.core.exceptions import (
    DuplicateWebhookError,
    MemoryStoreError,
    WebhookParseError,
    WebhookValidationError,
)
from backend.webhook_receiver.validator import validate_github_signature
from backend.webhook_receiver.parser import parse_webhook_payload
from backend.job_queue.arq_worker import enqueue_review_job
from backend.config.settings import Settings, get_settings

logger = logging.getLogger(__name__)


router = APIRouter(
    prefix = "/webhook",
    tags = ["webhook"],
)

@router.post(
    "/github",
    status_code = status.HTTP_200_OK,
    summary = "Github webhook receiver",
    description = (
        "Receives GitHub pull_request webhook events. "
        "Validates HMAC signature, parses payload, enqueues review job."
    ),
)

async def receive_github_webhook(
    request: Request,
    # Fastpi reads these from the request header automatically
    x_hub_signature_256: str | None = Header(default=None),
    x_github_event: str | None = Header(default=None),
    cfg: Settings = Depends(get_settings),
) -> JSONResponse:
    """
     Receives and processes a GitHub webhook event.

    GitHub sends this when a pull request is opened, updated, or reopened.
    We validate the signature, parse the payload, deduplicate, and enqueue.
    The actual review runs asynchronously — we return 200 immediately.

    CONTRACT:
      Precondition:
        - request body must be valid JSON
        - X-Hub-Signature-256 header must be present and correct
        - X-GitHub-Event header should be present
      Postcondition:
        - Returns 200 in all non-error cases (even for ignored event types)
        - Returns 401 only when signature is invalid (not from GitHub)
        - Returns 400 only when payload is malformed JSON
        - Never returns 500 for business logic errors (only unhandled exceptions)
    """

    raw_body = await request.body()

    try:
        validate_github_signature(
            payload_bytes = raw_body,
            signature_header = x_hub_signature_256,
            secret = cfg.github_webhook_secret
        ) # return None on successfull validation OR raise WebhookValidationError on failure
    except WebhookValidationError as e:
        logger.warning("Webhook signature validation failed: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature.",
        ) from e

    
    try:
        event = parse_webhook_payload(
            raw_body = raw_body,
            event_type_header = x_github_event
        )
    except WebhookParseError as e:
        logger.error("WeWebhook payload parse error: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not parse webhook payload: {str(e)}",
        ) from e

    if event is None:
        logger.debug(
            "Ignoring webhook event type '%s' — not a pull_request event.",
            x_github_event,
        )

        return JSONResponse(
            content={"status": "ignored", "reason": "event type not handled"},
            status_code=status.HTTP_200_OK,
        )
    
    logger.info(
        "Received pull_request webhook | repo=%s pr=%d action=%s commit=%s",
        event.repo_full_name,
        event.pr_number,
        event.action,
        event.head_commit_sha[:8],   # log only first 8 chars of the SHA
    )

    try:
        await enqueue_review_job(
            workflow_id=event.idempotency_key,
            input_data={
                "repo_full_name": event.repo_full_name,
                "pr_number": event.pr_number,
                "pr_title": event.pr_title,
                "pr_body": event.pr_body,
                "author_login": event.author_login,
                "head_commit_sha": event.head_commit_sha,
                "base_branch": event.base_branch,
                # Pass diff inline if the webhook payload contains it.
                # Used as fallback when GitHub API is unavailable (local demo).
                "pr_diff": event.pull_request.diff if hasattr(event.pull_request, "diff") else "",
            },
        )
    
    except DuplicateWebhookError:
        logger.info(
            "Duplicate webhook ignored | idempotency_key=%s",
            event.idempotency_key,
        )
        return JSONResponse(
            content={"status": "already_queued", "idempotency_key": event.idempotency_key},
            status_code=status.HTTP_200_OK,
        )
    except MemoryStoreError as e:
        logger.error("Redis unavailable during enqueue: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Job queue temporarily unavailable. Please retry.",
        ) from e
    
    return JSONResponse(
        content={
            "status": "queued",
            "repo": event.repo_full_name,
            "pr_number": event.pr_number,
            "commit_sha": event.head_commit_sha,
        },
        status_code=status.HTTP_200_OK,
    )