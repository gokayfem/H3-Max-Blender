from __future__ import annotations

import tempfile
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import bpy  # type: ignore[import-not-found]

from .utils import requires_internet_access

# ---------------------------------------------------------------------------
# Thread pool — shared across all jobs
# ---------------------------------------------------------------------------
_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="fal")


# ---------------------------------------------------------------------------
# Error formatting (module-level helper)
# ---------------------------------------------------------------------------
def _format_error(e: Exception) -> str:
    """Extract useful error details from fal_client exceptions."""
    error_type = type(e).__name__
    msg = str(e)

    status_code = getattr(e, "status_code", None) or getattr(e, "status", None)
    body = getattr(e, "body", None) or getattr(e, "detail", None)

    response = getattr(e, "response", None)
    if response is not None:
        if status_code is None:
            status_code = getattr(response, "status_code", None)
        if body is None:
            try:
                body = response.json()
            except Exception:
                try:
                    body = response.text[:500]
                except Exception:
                    pass

    parts = []
    if status_code:
        parts.append(f"HTTP {status_code}")
    if body:
        if isinstance(body, dict):
            detail = body.get("detail") or body.get("message") or body.get("error")
            if isinstance(detail, str):
                parts.append(detail)
            elif isinstance(detail, list) and detail:
                parts.append("; ".join(d.get("msg", str(d)) for d in detail[:3]))
            else:
                parts.append(str(body)[:300])
        else:
            parts.append(str(body)[:300])
    elif msg and msg != str(status_code):
        parts.append(msg[:300])

    if parts:
        return f"{error_type}: {' — '.join(parts)}"
    return f"{error_type}: {msg[:300]}"


# ---------------------------------------------------------------------------
# FalJob
# ---------------------------------------------------------------------------
class FalJob:
    """
    Tracks a single fal API request running in a background thread.
    """

    def __init__(
        self,
        endpoint: str,
        arguments: dict[str, Any],
        on_complete: Callable[["FalJob"], None],
        *,
        job_id: str | None = None,
        label: str = "",
        download_keys: list[str] | None = None,
    ) -> None:
        """Initialize a FalJob.

        Args:
            endpoint: The API endpoint to call.
            arguments: The arguments to pass to the API endpoint.
            on_complete: The function to call when the job is complete.
            job_id: The ID of the job.
            label: The label of the job.
            download_keys: The keys to download from the result. Defaults to an empty list.
                Supports dotted paths like 'model_mesh.url' and
                array access like 'images.0.url'.
        """
        self.job_id = job_id or uuid.uuid4().hex[:12]
        self.endpoint = endpoint
        self.arguments = arguments
        self.on_complete = on_complete
        self.label = label or endpoint
        self.download_keys = download_keys or []

        self.status: str = "pending"  # pending | running | complete | error
        self.progress: float = 0.0
        self.progress_message: str = ""
        self.result: dict[str, Any] | None = None
        self.downloaded_files: dict[str, str] = {}  # key → local path
        self.error: str | None = None
        self.request_id: str | None = None  # fal request ID for server-side debugging
        self.start_time: float | None = None  # time.time() when job started
        self.end_time: float | None = None  # time.time() when job completed
        self._future = None
        self._api_key: str | None = None  # cached on main thread before submit

    # ── Lifecycle ──────────────────────────────────────────────────────

    @requires_internet_access
    def submit(self) -> None:
        """
        Submit the job to the thread pool.

        MUST be called from the main thread — caches the API key
        before spawning the background thread.
        """
        from .preferences import get_api_key

        self._api_key = get_api_key()
        if not self._api_key:
            self.error = "No fal.ai API key configured. Set it in Edit > Preferences > Add-ons > fal.ai, or set the FAL_KEY environment variable."
            self.status = "error"
            print(f"fal.ai: {self.error}")
            return

        self.status = "running"
        self.start_time = time.time()
        self._future = _executor.submit(self._run)

    def _run(self) -> None:
        """
        Execute in background thread — no bpy calls allowed here!
        """
        try:
            import fal_client
        except ImportError as e:
            self.error = f"fal_client not installed: {e}"
            self.status = "error"
            print(f"fal.ai: {self.error}")
            return

        try:
            client = fal_client.SyncClient(key=self._api_key)

            def _on_queue_update(update) -> None:
                if isinstance(update, fal_client.InProgress):
                    if update.logs:
                        last = update.logs[-1]
                        msg = (
                            last.get("message", "")
                            if isinstance(last, dict)
                            else str(last)
                        )
                        self.progress_message = msg[:80]

            def _on_enqueue(request_id: str) -> None:
                self.request_id = request_id
                print(f"fal.ai: {self.endpoint} enqueued as {request_id}")

            print(
                f"fal.ai: Calling {self.endpoint} "
                f"with {list(self.arguments.keys())}"
            )
            result = client.subscribe(
                self.endpoint,
                arguments=self.arguments,
                with_logs=True,
                on_enqueue=_on_enqueue,
                on_queue_update=_on_queue_update,
            )
            self.result = result
            print(
                f"fal.ai: {self.endpoint} [{self.request_id or '?'}] returned: "
                f"{list(result.keys()) if isinstance(result, dict) else type(result)}"
            )

            self._download_results(result)
            self.status = "complete"
            self.end_time = time.time()

        except Exception as e:
            self.error = _format_error(e)
            self.status = "error"
            if self.request_id:
                self.error = f"[{self.request_id}] {self.error}"
            self.end_time = time.time()
            print(
                f"fal.ai: Job {self.job_id} [{self.request_id or '?'}] failed: {self.error}"
            )
            traceback.print_exc()

    @requires_internet_access
    def _download_results(self, result: dict[str, Any]) -> None:
        """
        Download URLs from result dict to local temp files.

        Args:
            result: The result from the API call.
        """
        import urllib.request

        for key in self.download_keys:
            url = self._extract_url(result, key)
            if not url:
                continue

            ext = Path(url.split("?")[0]).suffix or ".bin"
            tmp = tempfile.NamedTemporaryFile(
                prefix=f"fal_{self.job_id}_",
                suffix=ext,
                delete=False,
            )
            tmp.close()

            try:
                urllib.request.urlretrieve(url, tmp.name)
                self.downloaded_files[key] = tmp.name
            except Exception as e:
                print(f"fal.ai: Failed to download {key}: {e}")

    @staticmethod
    def _extract_url(data: Any, key: str) -> str | None:
        """
        Extract a URL from nested result data.

        Supports dotted paths like 'model_mesh.url' and
        array access like 'images.0.url'.

        Args:
            data: The data to extract the URL from.
            key: The key to extract the URL from.

        Returns:
            The URL if found, otherwise None.

        Raises:
            ValueError: If the key is not a valid URL.
        """
        parts = key.split(".")
        current = data
        for part in parts:
            if current is None:
                return None
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, (list, tuple)):
                try:
                    current = current[int(part)]
                except (IndexError, ValueError):
                    return None
            else:
                return None
        return current if isinstance(current, str) else None

    @property
    def is_done(self) -> bool:
        """Check if the job is done."""
        return self.status in ("complete", "error")

    @property
    def duration_seconds(self) -> float | None:
        """Get job duration in seconds, or None if not completed."""
        if self.start_time is None:
            return None
        end = self.end_time or time.time()
        return end - self.start_time

    @property
    def duration_str(self) -> str:
        """Get formatted duration string like '1.2s' or '1m 23s'."""
        dur = self.duration_seconds
        if dur is None:
            return ""
        if dur < 60:
            return f"{dur:.1f}s"
        mins = int(dur // 60)
        secs = int(dur % 60)
        return f"{mins}m {secs}s"

    @property
    def start_time_str(self) -> str:
        """Get formatted start time like '6:45 PM'."""
        if self.start_time is None:
            return ""
        dt = datetime.fromtimestamp(self.start_time)
        return f"{dt.hour % 12 or 12}:{dt.minute:02d} {'AM' if dt.hour < 12 else 'PM'}"

    @property
    def endpoint_short(self) -> str:
        """Get shortened endpoint name (last component)."""
        parts = self.endpoint.strip("/").split("/")
        # e.g. fal-ai/flux-2/klein/9b/edit -> klein/9b/edit or just the last 2-3 parts
        if len(parts) > 2:
            return "/".join(parts[-2:])
        return parts[-1] if parts else self.endpoint


# ---------------------------------------------------------------------------
# JobManager singleton
# ---------------------------------------------------------------------------
class JobManager:
    """
    Manages active fal jobs, polls completion via bpy.app.timers.
    """

    _instance: JobManager | None = None

    def __init__(self) -> None:
        """
        Initialize a JobManager.

        Args:
            jobs: The jobs to manage.
            history: The history of jobs.
            _timer_running: Whether the timer is running.
            _max_history: The maximum number of jobs to keep in history.
        """
        self.jobs: dict[str, FalJob] = {}
        self.history: list[FalJob] = []
        self._timer_running = False
        self._max_history = 20

    @classmethod
    def get(cls) -> JobManager:
        """
        Get the singleton instance of JobManager.
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """
        Reset the singleton (for testing / unregister).
        """
        cls._instance = None

    def submit(self, job: FalJob) -> FalJob:
        """
        Submit a job for execution. Must be called from main thread.

        Args:
            job: The job to submit.

        Returns:
            The submitted job.
        """
        self.jobs[job.job_id] = job
        job.submit()  # raises RuntimeError if internet access is not allowed
        if not self._timer_running:
            bpy.app.timers.register(self._poll, first_interval=0.5)
            self._timer_running = True
        return job

    def cancel(self, job_id: str) -> bool:
        """
        Cancel a pending/running job (best-effort).

        Args:
            job_id: The ID of the job to cancel.

        Returns:
            True if the job was cancelled, False otherwise.
        """
        job = self.jobs.get(job_id)
        if job and job._future:
            job._future.cancel()
            job.status = "error"
            job.error = "Cancelled"
            return True
        return False

    def _poll(self) -> float | None:
        """
        Timer callback — runs on the main thread.

        Returns:
            The time to wait until the next poll, or None if no jobs are left.
        """
        done_ids = []

        # Snapshot keys — on_complete handlers may submit new jobs
        for job_id in list(self.jobs):
            job = self.jobs.get(job_id)
            if job is None or not job.is_done:
                continue
            done_ids.append(job_id)
            self.history.append(job)
            if len(self.history) > self._max_history:
                self.history.pop(0)
            try:
                job.on_complete(job)
            except Exception as e:
                print(f"fal.ai: Error in completion handler: {e}")
                traceback.print_exc()

        for jid in done_ids:
            self.jobs.pop(jid, None)

        if self.jobs:
            try:
                for window in bpy.context.window_manager.windows:
                    for area in window.screen.areas:
                        if area.type == "VIEW_3D":
                            area.tag_redraw()
            except Exception:
                pass
            return 0.5
        else:
            self._timer_running = False
            return None

    @property
    def active_count(self) -> int:
        """
        Get the number of active jobs.
        """
        return len(self.jobs)

    @property
    def active_jobs(self) -> list[FalJob]:
        """
        Get the list of active jobs.
        """
        return list(self.jobs.values())
