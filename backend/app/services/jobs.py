"""In-memory background jobs for long valuations.

Render's proxy drops requests after ~60s and a cold vehicle can take longer than
that on a small instance, so the browser starts a job and polls it for progress.
Single-process only (jobs live in this process's memory), which matches the
one-instance deployment.
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

JOB_TTL_SECONDS = 15 * 60


@dataclass
class Job:
    id: str
    total: int = 0
    done: int = 0
    status: str = "running"  # running | done | error
    result: Any = None
    error: str = ""
    created: float = field(default_factory=time.time)

    def progress(self, done: int, total: int) -> None:
        self.done, self.total = done, total


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def start(self, fn: Callable[[Job], Any], total: int = 0) -> Job:
        job = Job(id=uuid.uuid4().hex[:12], total=total)
        with self._lock:
            self._sweep()
            self._jobs[job.id] = job

        def run() -> None:
            try:
                job.result = fn(job)
                job.status = "done"
            except Exception as exc:  # surfaced to the poller, never raised in the thread
                job.error = f"{type(exc).__name__}: {exc}"
                job.status = "error"

        threading.Thread(target=run, name=f"job-{job.id}", daemon=True).start()
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def _sweep(self) -> None:
        cutoff = time.time() - JOB_TTL_SECONDS
        for jid in [j for j, job in self._jobs.items() if job.created < cutoff and job.status != "running"]:
            del self._jobs[jid]
