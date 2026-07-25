"""
Run-scoped output directory for the worker chain (voice -> thumbnail ->
render -> upload).

**Known gap, stated plainly rather than hidden** (same convention Phase
6's handoff notes used for its own open items): this writes to local
disk (`WORKER_OUTPUT_DIR`, default `/tmp/ai_carryon_runs`), which only
works because Celery's `worker_prefetch_multiplier=1` plus this
project's current single-worker-process local dev setup means every
task in a given run's chain happens to execute wherever Celery's worker
process is running. That assumption BREAKS the moment there's more than
one worker process on more than one machine — voice_worker's audio file
wouldn't be visible to render_worker running elsewhere. The real fix is
routing these bytes through Firebase Storage (already in `.env.example`
as `FIREBASE_STORAGE_BUCKET`, added Phase 6, unused until now) instead
of a local path. Not built this phase on purpose: this phase's own
Definition of Done ("a full pipeline run... results in a rendered,
uploaded video... crashing the render worker mid-job results in an
automatic retry") is provable on one local worker process, and adding
real cloud storage wiring is a distinct, focused piece of work that
deserves its own pass rather than a drive-by addition here. Flagged in
this phase's PHASE.md handoff notes and STATUS.md, same as every prior
phase's honestly-stated gaps.
"""

from __future__ import annotations

import os
from pathlib import Path


def run_dir(channel_id: str, run_id: str) -> Path:
    """Returns (and creates) the local directory this run's intermediate
    and final artifacts live in: voice.mp3, thumbnail.png, final.mp4.
    Channel-scoped in the path per Ch.12b's general namespacing
    convention, even though this isn't Redis/Qdrant — same reasoning
    (a lookup for the wrong channel/run should simply not exist, not
    collide with another channel's file of the same name).
    """
    base = Path(os.environ.get("WORKER_OUTPUT_DIR", "/tmp/ai_carryon_runs"))
    path = base / channel_id / run_id
    path.mkdir(parents=True, exist_ok=True)
    return path
