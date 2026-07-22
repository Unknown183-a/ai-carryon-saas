Architecture Decision Records (ADRs) — one file per non-obvious technical choice, e.g. "why
Celery + Redis over Cloud Tasks," "why Upstash over self-hosted Redis." Optional, but cheaper
than re-litigating a decision six months later. Suggested filename: `NNNN-short-title.md`
(e.g. `0001-task-queue-choice.md`). Not the same as `../../work-reports/milestones/` — a
decision record explains *why*, a milestone report says *what shipped*.
