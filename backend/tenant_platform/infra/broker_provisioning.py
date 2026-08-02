"""
Automatic per-channel Celery broker provisioning (closes the manual gap
in docs/deployment/README.md's isolation runbook).

Triggered from PATCH /channels/{id}/provider-keys whenever a request
includes a non-empty `celery_broker_url` — the same moment a user
rotates/sets it via the Providers UI. Two API calls replace what used to
be: (1) a human creating a Secret Manager secret by hand, (2) a human
editing deploy.yml's matrix and pushing to trigger CI. Neither GCP
Console nor GitHub access is needed by the calling user for either step.

This does NOT provision the Upstash database itself — Upstash's own API
requires a separate account-level API key this project doesn't hold
yet, and provisioning a paid-tier-capable database on a user's behalf
raises billing questions worth deciding deliberately, not baking into
a background task. A user still gets their own rediss:// string from
Upstash's console themselves; this module takes over from the moment
they paste that string into the Providers screen.
"""

from __future__ import annotations

import logging
import re

from google.api_core.exceptions import AlreadyExists, NotFound
from google.cloud import run_v2, secretmanager

logger = logging.getLogger(__name__)

_SHARED_SECRET_CANDIDATES = [
    "FIREBASE_SERVICE_ACCOUNT_JSON", "UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN",
    "QDRANT_URL", "QDRANT_API_KEY", "CHANNEL_SECRETS_ENCRYPTION_KEY", "GEMINI_API_KEY",
    "GROQ_API_KEY", "OPENAI_API_KEY", "YOUTUBE_CLIENT_SECRETS_B64", "YOUTUBE_TOKEN_B64",
    "ELEVENLABS_API_KEY", "INTERNAL_SCHEDULER_TOKEN", "SERPER_API_KEY", "PEXELS_API_KEY",
    "YOUTUBE_OAUTH_REDIRECT_URI", "FRONTEND_URL",
]

_IMAGE = "ghcr.io/unknown183-a/ai-carryon-saas:latest"
_REGION = "asia-south1"


def _secret_name_for_channel(channel_id: str) -> str:
    return f"CELERY_BROKER_URL__{channel_id.upper()}"


def _service_name_for_channel(channel_id: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", channel_id.lower()).strip("-")
    name = f"ai-carryon-worker-{slug}"
    return name[:63].rstrip("-")


def ensure_broker_secret(project_id: str, channel_id: str, broker_url: str) -> str:
    client = secretmanager.SecretManagerServiceClient()
    secret_name = _secret_name_for_channel(channel_id)
    parent = f"projects/{project_id}"
    secret_path = f"{parent}/secrets/{secret_name}"

    try:
        client.get_secret(name=secret_path)
    except NotFound:
        client.create_secret(
            parent=parent,
            secret_id=secret_name,
            secret={"replication": {"automatic": {}}},
        )
        logger.info("Created Secret Manager secret %s", secret_name)

    client.add_secret_version(
        parent=secret_path,
        payload={"data": broker_url.encode("utf-8")},
    )
    logger.info("Added new version to %s", secret_name)
    return secret_name


def ensure_channel_worker(project_id: str, channel_id: str, broker_secret_name: str) -> str:
    client = run_v2.ServicesClient()
    service_id = _service_name_for_channel(channel_id)
    parent = f"projects/{project_id}/locations/{_REGION}"
    service_path = f"{parent}/services/{service_id}"

    secret_client = secretmanager.SecretManagerServiceClient()

    def _secret_exists(name: str) -> bool:
        try:
            secret_client.get_secret(name=f"projects/{project_id}/secrets/{name}")
            return True
        except NotFound:
            return False

    env_vars = [run_v2.EnvVar(name="FIREBASE_PROJECT_ID", value=project_id)]
    secret_env = [
        ("CELERY_BROKER_URL", broker_secret_name),
        *[(var, var) for var in _SHARED_SECRET_CANDIDATES if _secret_exists(var)],
    ]
    for env_name, secret_name in secret_env:
        env_vars.append(
            run_v2.EnvVar(
                name=env_name,
                value_source=run_v2.EnvVarSource(
                    secret_key_ref=run_v2.SecretKeySelector(secret=secret_name, version="latest")
                ),
            )
        )

    container = run_v2.Container(
        image=_IMAGE,
        command=["python", "-m"],
        args=["app.workers.worker_entrypoint"],
        ports=[run_v2.ContainerPort(container_port=8080)],
        env=env_vars,
        resources=run_v2.ResourceRequirements(
            limits={"cpu": "2", "memory": "8Gi"},
            cpu_idle=False,
        ),
    )

    service = run_v2.Service(
        template=run_v2.RevisionTemplate(
            containers=[container],
            scaling=run_v2.RevisionScaling(min_instance_count=1, max_instance_count=1),
        ),
        ingress=run_v2.IngressTraffic.INGRESS_TRAFFIC_INTERNAL_ONLY,
    )

    try:
        client.create_service(parent=parent, service=service, service_id=service_id)
        logger.info("Kicked off create for worker service %s (channel %s) — deploy runs "
                     "in the background, check Cloud Run console/logs for completion", service_id, channel_id)
    except AlreadyExists:
        service.name = service_path
        client.update_service(service=service)
        logger.info("Kicked off update for worker service %s (channel %s) — deploy runs "
                     "in the background, check Cloud Run console/logs for completion", service_id, channel_id)

    return service_id


def provision_channel_broker(project_id: str, channel_id: str, broker_url: str) -> None:
    try:
        secret_name = ensure_broker_secret(project_id, channel_id, broker_url)
        ensure_channel_worker(project_id, channel_id, secret_name)
    except Exception:
        logger.exception(
            "Automatic broker provisioning failed for channel %s — the broker URL was saved, "
            "but no dedicated worker is running yet. Needs manual follow-up (see the isolation "
            "runbook) until this is retried.",
            channel_id,
        )
