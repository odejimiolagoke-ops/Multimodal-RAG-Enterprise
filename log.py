import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

AUDIT_LOG_PATH = Path(__file__).resolve().parent / "enterprise_audit.log"

logger = logging.getLogger("enterprise.audit")
logger.setLevel(logging.INFO)
logger.propagate = False

if not any(
    isinstance(handler, logging.FileHandler)
    and Path(handler.baseFilename) == AUDIT_LOG_PATH
    for handler in logger.handlers
):
    audit_handler = logging.FileHandler(AUDIT_LOG_PATH, encoding="utf-8")
    audit_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(audit_handler)


def register_logging_middleware(app):
    @app.middleware("http")
    async def log_requests(request, call_next):
        start_time = time.perf_counter()
        status_code = 500
        error_type = None

        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception as exc:
            error_type = type(exc).__name__
            raise
        finally:
            event = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "user": getattr(request.state, "user", "anonymous"),
                "role": getattr(request.state, "role", "guest"),
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
                "outcome": "success" if status_code < 400 else "failure",
                "duration_seconds": round(time.perf_counter() - start_time, 6),
            }
            if error_type is not None:
                event["error_type"] = error_type
            logger.info(json.dumps(event, separators=(",", ":")))

    return app
