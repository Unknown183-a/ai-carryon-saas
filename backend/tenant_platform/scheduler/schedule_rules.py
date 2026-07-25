"""
Schedule timing rules (Ch.16, Phase 8).

PHASE.md's task list says: "Reuse the existing 9 AM IST Railway
scheduler's logic/timing as the reference implementation — don't
redesign the scheduling rules from scratch." Worth being precise about
what that means here, the same way Phase 7's handoff was precise about
"verified structurally" vs "verified functionally": the *old* Railway
pipeline's actual cron source isn't part of this repo (this repo is a
from-scratch rebuild per `BUILD_GUIDE.md`'s intro, not a port of that
codebase's files), so "reuse its logic/timing" is implemented here as
"reuse its one documented, load-bearing rule" — a single daily run at
09:00 IST — rather than inventing a new default. `ChannelCreateRequest`
(Phase 6, `app/models/channel.py`)'s `upload_schedule` field already
carries a small enum of frequencies (`"1_per_day"` is the default);
this module is what turns that string into an actual next-run-at
instant, generalizing 09:00 IST from "the one frequency the old
pipeline had" to "the default time of day for whichever frequency a
channel picks."

Every computation here works in UTC internally (matches everything else
this project stores in Firestore — see `firestore_collections.py`'s
`_now_iso()`) and only touches `Asia/Kolkata` at the point of deciding
what "09:00 local" means. `zoneinfo` (stdlib since Python 3.9) needs no
new dependency — this project already requires 3.11+ per `STATUS.md`'s
prerequisites checklist.
"""

from __future__ import annotations

import datetime
from zoneinfo import ZoneInfo

DEFAULT_TIMEZONE = "Asia/Kolkata"
DEFAULT_TIME_OF_DAY = "09:00"  # the old pipeline's one rule, per this module's docstring

# `upload_schedule` -> the weekdays it runs on (Monday=0 .. Sunday=6).
# Everything reuses the 09:00 IST time-of-day; only the day-set changes.
# An unrecognized value falls back to daily — see `weekdays_for()` below —
# rather than silently never running, which would be a much worse failure
# mode for a channel someone is paying attention to.
_FREQUENCY_WEEKDAYS: dict[str, tuple[int, ...]] = {
    "1_per_day": (0, 1, 2, 3, 4, 5, 6),
    "daily": (0, 1, 2, 3, 4, 5, 6),
    "5_per_week": (0, 1, 2, 3, 4),  # weekdays
    "3_per_week": (0, 2, 4),  # Mon/Wed/Fri
    "1_per_week": (0,),  # Monday
}


def weekdays_for(upload_schedule: str) -> tuple[int, ...]:
    """Returns the tuple of weekdays (Monday=0) this `upload_schedule`
    value runs on. Unknown/custom values fall back to daily — see the
    module docstring's note on why "run more often than expected" is the
    safer failure mode than "silently never runs."
    """
    return _FREQUENCY_WEEKDAYS.get(upload_schedule, _FREQUENCY_WEEKDAYS["1_per_day"])


def compute_next_run_at(
    upload_schedule: str,
    after: datetime.datetime,
    time_of_day: str = DEFAULT_TIME_OF_DAY,
    timezone: str = DEFAULT_TIMEZONE,
) -> datetime.datetime:
    """Returns the next UTC instant, strictly after `after`, that matches
    this schedule. `after` must be timezone-aware (naive datetimes are a
    common source of silent off-by-hours bugs — see Ch.16's own note on
    why the old pipeline's scheduler bugs were almost always timezone
    bugs, not logic bugs).
    """
    if after.tzinfo is None:
        raise ValueError("compute_next_run_at requires a timezone-aware `after` datetime")

    tz = ZoneInfo(timezone)
    hour, minute = (int(part) for part in time_of_day.split(":"))
    allowed_weekdays = weekdays_for(upload_schedule)

    local_after = after.astimezone(tz)
    candidate = local_after.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= local_after:
        candidate += datetime.timedelta(days=1)

    # Walk forward (at most 7 days) to the next allowed weekday.
    for _ in range(8):
        if candidate.weekday() in allowed_weekdays:
            return candidate.astimezone(datetime.timezone.utc)
        candidate += datetime.timedelta(days=1)

    # Unreachable unless _FREQUENCY_WEEKDAYS is ever misconfigured with an
    # empty tuple — fail loudly rather than looping forever.
    raise ValueError(f"No matching weekday found for upload_schedule={upload_schedule!r}")


def is_due(schedule_doc: dict, now: datetime.datetime) -> bool:
    """A schedule is due when it's enabled and its stored `next_run_at`
    (ISO 8601, UTC) is not in the future. Missing/malformed `next_run_at`
    is treated as "not due" (fail closed — a channel with a broken
    schedule document should sit idle, not fire every time the Scheduler
    polls), never as "always due."
    """
    if not schedule_doc.get("enabled", True):
        return False

    next_run_at_raw = schedule_doc.get("next_run_at")
    if not next_run_at_raw:
        return False

    try:
        next_run_at = datetime.datetime.fromisoformat(next_run_at_raw)
    except (TypeError, ValueError):
        return False

    if next_run_at.tzinfo is None:
        next_run_at = next_run_at.replace(tzinfo=datetime.timezone.utc)

    return next_run_at <= now
