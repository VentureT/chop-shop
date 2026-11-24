import time

from app.services.jobs import JobStore


def _wait(job, timeout=2.0):
    t0 = time.time()
    while job.status == "running" and time.time() - t0 < timeout:
        time.sleep(0.01)
    return job


def test_job_runs_in_background_and_reports_progress():
    store = JobStore()

    def work(job):
        for i in range(3):
            job.progress(i + 1, 3)
        return {"ok": True}

    job = store.start(work, total=3)
    assert store.get(job.id) is job
    _wait(job)
    assert job.status == "done" and job.result == {"ok": True} and (job.done, job.total) == (3, 3)


def test_job_error_is_captured():
    store = JobStore()

    def boom(job):
        raise RuntimeError("eBay down")

    job = _wait(store.start(boom))
    assert job.status == "error" and "eBay down" in job.error and job.result is None
    assert store.get("nope") is None
