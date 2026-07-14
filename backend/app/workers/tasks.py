"""Worker entrypoint module — re-exports every Celery task so `celery -A
app.workers.celery_app worker` discovers them from a single place."""

from app.eval.financebench_runner import run_financebench_task
from app.ingest.pipeline import ingest_document

__all__ = ["ingest_document", "run_financebench_task"]
