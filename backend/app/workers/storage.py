"""
Run-scoped output directory *and* cross-worker persistence for the
worker chain (voice -> thumbnail -> render -> upload).

**Fixes the gap this module used to flag as known-and-deferred**: local
disk alone (`WORKER_OUTPUT_DIR`, default `/tmp/ai_carryon_runs`) only
works when every task in a run's chain happens to execute on the same
container. On Cloud Run that assumption breaks the moment an instance
gets recycled mid-chain (e.g. right after a broker reconnect) — a later
step's container has an empty `/tmp` and can't see an earlier step's
output file, even though `run_dir()` would happily "find" its own
freshly-created empty directory instead of raising a clear error.

The fix: every worker still writes/reads through `run_dir()` on local
disk — ffmpeg and Pillow need real files, not blobs — but the moment a
file is a chain *output* another task depends on, that task also calls
`persist()` to copy it into Firebase Storage (`FIREBASE_STORAGE_BUCKET`,
wired into `init_firebase()` in `app/api/middleware/auth.py`) and passes
the returned `firebase://...` reference along in the payload instead of
a bare local path. Whichever task consumes that reference next calls
`ensure_local()`, which downloads from Storage only if the file isn't
already sitting on that container's local disk — so a single-worker dev
setup (the common case today) never pays a network round trip, and it's
only the recycled-instance case that actually needs one.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_STORAGE_PREFIX = "firebase://"


def run_dir(channel_id: str, run_id: str) -> Path:
    """Returns (and creates) the local directory this run's intermediate
    and final artifacts live in: voice.mp3, thumbnail.png, clip_*.mp4,
    final.mp4. Channel-scoped in the path per Ch.12b's general
    namespacing convention, even though this isn't Redis/Qdrant — same
    reasoning (a lookup for the wrong channel/run should simply not
    exist, not collide with another channel's file of the same name).
    """
    base = Path(os.environ.get("WORKER_OUTPUT_DIR", "/tmp/ai_carryon_runs"))
    path = base / channel_id / run_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _bucket():
    """Lazily resolves the Firebase Storage bucket off the *same*
    firebase_admin app Auth/Firestore already use, initializing it via
    `init_firebase()` if this is the first Firebase call this process
    has made — a worker process may never have hit an authenticated API
    route and so never triggered that initialization itself.
    """
    from firebase_admin import storage as fb_storage

    from app.api.middleware.auth import init_firebase

    init_firebase()
    return fb_storage.bucket()


def _blob_path(channel_id: str, run_id: str, filename: str) -> str:
    return f"runs/{channel_id}/{run_id}/{filename}"


def persist(local_path: Path, channel_id: str, run_id: str) -> str:
    """Uploads a just-written local artifact to Firebase Storage and
    returns a `firebase://<blob path>` reference for later chain steps
    to resolve via `ensure_local()`. The local file is left in place —
    if the next step happens to run on this same container (the common
    case), `ensure_local()` will find it there and skip the download.
    """
    blob_path = _blob_path(channel_id, run_id, local_path.name)
    blob = _bucket().blob(blob_path)
    blob.upload_from_filename(str(local_path))
    logger.info("storage.persist: %s -> firebase://%s", local_path, blob_path)
    return f"{_STORAGE_PREFIX}{blob_path}"


def ensure_local(path_or_ref: str, channel_id: str, run_id: str) -> Path:
    """Resolves a payload field that may be a local filesystem path
    (written by, and this task running on, the same container) or a
    `firebase://...` reference (written by a different container) into
    a local file this process can hand to ffmpeg/ffprobe/the YouTube
    upload call.

    Also covers a plain local path left behind by a container that has
    since been recycled: instead of failing outright, it retries under
    the same channel/run/filename convention `persist()` always writes
    to, so an older-format path still resolves correctly.
    """
    if path_or_ref.startswith(_STORAGE_PREFIX):
        blob_path = path_or_ref[len(_STORAGE_PREFIX):]
        filename = Path(blob_path).name
    else:
        local_path = Path(path_or_ref)
        if local_path.exists():
            return local_path
        filename = local_path.name
        blob_path = _blob_path(channel_id, run_id, filename)

    dest = run_dir(channel_id, run_id) / filename
    if dest.exists():
        return dest

    blob = _bucket().blob(blob_path)
    blob.download_to_filename(str(dest))
    logger.info("storage.ensure_local: firebase://%s -> %s", blob_path, dest)
    return dest
