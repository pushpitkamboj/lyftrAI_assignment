import time
import uuid
import json
from fastapi import Request
from datetime import datetime, timezone

async def log_requests(request: Request, call_next):
    start_time = time.time()
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    process_time = (time.time() - start_time) * 1000
    log_data = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": "INFO" if response.status_code < 400 else "ERROR",
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
        "status": response.status_code,
        "latency_ms": round(process_time, 2)
    }
    extra_info = getattr(request.state, "extra_info", {})
    log_data.update(extra_info)
    print(json.dumps(log_data))
    return response