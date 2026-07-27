"""
Phase 9 — Cloud Run worker entrypoint.

Cloud Run expects a container to listen on $PORT and answer HTTP requests to
be considered healthy — that's how it decides an instance is up, and (with
--min-instances=1 --no-cpu-throttling) how it justifies keeping that instance
running and billed with no incoming requests. A Celery worker doesn't listen
on any port on its own — it just polls Redis in a loop — so without this
shim, Cloud Run would consider the worker container unhealthy and keep
cycling it.

This process does two things:
  1. Starts the real Celery worker as a child process — same command as
     docker-compose.yml's local dev worker service.
  2. Runs a tiny HTTP server on $PORT that always replies 200 OK, purely so
     Cloud Run's health checks pass. It carries no other meaning — it does
     NOT reflect whether Celery is actually consuming tasks.

SIGTERM (Cloud Run's shutdown signal) is forwarded to the Celery child so
in-flight tasks get Celery's own graceful-shutdown handling, rather than
being hard-killed the moment this wrapper process exits.

Only used in the Cloud Run deploy path (see .github/workflows/deploy.yml's
worker deploy step, --command/--args). Local dev via docker-compose.yml
runs plain `celery -A app.workers.celery_app worker` instead — no Cloud Run,
no health polling, no need for this wrapper there.
"""
import os
import signal
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# --concurrency=1: video rendering (FFmpeg encode + mux) is memory-hungry
# enough on its own that letting Celery's default prefork pool spin up one
# worker process per vCPU (concurrency=4 on this service's 2 vCPUs) caused
# repeated OOM kills mid-render even at 2Gi -- multiple renders sharing one
# container's memory pool. Capping to 1 means a render task gets the whole
# container to itself; throughput for concurrent renders should come from
# scaling instances (--max-instances), not from packing more prefork workers
# into one container.
CELERY_CMD = [
    "celery", "-A", "app.workers.celery_app", "worker", "--loglevel=info",
    "--concurrency=1",
]


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args):
        pass  # keep Cloud Run's health polling out of the real worker logs


def _serve_health(port: int) -> None:
    HTTPServer(("0.0.0.0", port), _HealthHandler).serve_forever()


def main() -> None:
    port = int(os.environ.get("PORT", "8080"))
    threading.Thread(target=_serve_health, args=(port,), daemon=True).start()

    proc = subprocess.Popen(CELERY_CMD)

    def _forward_sigterm(signum, frame):
        proc.send_signal(signal.SIGTERM)

    signal.signal(signal.SIGTERM, _forward_sigterm)

    sys.exit(proc.wait())


if __name__ == "__main__":
    main()
