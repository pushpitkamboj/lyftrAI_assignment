import os
import logging
import datetime
from fastapi import FastAPI, HTTPException, Request, Header, Query
from fastapi.responses import JSONResponse
from sqlmodel import Session, select
from pydantic import BaseModel, Field, field_validator
from .models import messages, create_db_and_tables, engine
from .storage import insert_message
from .logging_utils import log_requests
from typing import Annotated, Optional
from sqlalchemy import text
import hmac
import hashlib


E164Phone = Annotated[str, Field(pattern=r"^\+\d+$")]
class WebhookPayload(BaseModel):
    message_id: str
    from_msisdn: E164Phone = Field(alias="from")
    to_msisdn: E164Phone = Field(alias="to")
    ts: str
    text: str | None = Field(default=None, max_length=4096)

    @field_validator("ts")
    @classmethod
    def validate_ts_strict_z(cls, v: str) -> str:
        if not v.endswith("Z"):
            raise ValueError("Timestamp must end with 'Z' (UTC suffix)")
        
        try:
            datetime.datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("Invalid ISO-8601 format")
            
        return v
    

app = FastAPI()
app.middleware("http")(log_requests)
logger = logging.getLogger("uvicorn.error")

def is_webhook_secret_set() -> bool:
    return bool(os.getenv("WEBHOOK_SECRET"))

def is_db_ready() -> bool:
    try:
        with Session(engine) as session:
            session.exec(text("SELECT 1 FROM messages LIMIT 1"))
        return True
    except Exception as e:
        logger.error(f"DB readiness check failed: {e}")
        return False
    
@app.on_event("startup")
def on_startup():
    try:
        create_db_and_tables()
    except Exception as e:
        raise Exception(f"the models could not be created successfully: {e}")

@app.get("/health/live")
def fit_check():
    return JSONResponse(
        content="live route working fine",
		status_code=200
	)
    
@app.get("/health/ready")
def ready_check():
    if not is_webhook_secret_set() or not is_db_ready():
        return JSONResponse(
            content="error",
			status_code=503
		)
    return JSONResponse(
        content="ready route working fine",
		status_code=200
	)
    
@app.post("/webhook")
async def webhook(
    request: Request,
	payload: WebhookPayload,
	x_signature: Annotated[str, Header()]
):
    body_bytes = await request.body()
    extra_info = {
        "result": None,
        "dup": False,
        "message_id": getattr(payload, "message_id", None)
    }
    
    if not is_webhook_secret_set():
        logger.error("Missing webhook secret")
        extra_info["result"] = "webhook missing"
        request.state.extra_info = extra_info
        raise HTTPException(status_code=401, detail="webhook missing")

    if not x_signature:
        logger.error("Missing X-Signature header")
        extra_info["result"] = "invalid_signature"
        request.state.extra_info = extra_info
        raise HTTPException(status_code=401, detail="invalid_signature")

    expected_signature = hmac.new(
    	key=os.getenv("WEBHOOK_SECRET").encode(),
    	msg=body_bytes,
    	digestmod=hashlib.sha256 
	).hexdigest()
    
    if not hmac.compare_digest(expected_signature, x_signature):
        logger.error("Invalid HMAC signature")
        extra_info["result"] = "invalid_signature"
        request.state.extra_info = extra_info
        raise HTTPException(status_code=401, detail="invalid_signature")

    try:
        with Session(engine) as db:
            res = insert_message(db, payload)
            extra_info.update({
                "result": res,
                "dup": res == "duplicate"
            })
            request.state.extra_info = extra_info
        return {"status": "ok"}
    
    except Exception as e:
        logger.error(f"Internal error: {str(e)}")
        extra_info["result"] = "validation_error"
        request.state.extra_info = extra_info
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/messages")
def get_messages(
    limit: int = Query(50, ge=1, le=100),
    offset: int | None = Query(0, ge=0),
    from_msisdn: str | None = Query(None, alias="from"),
    since: str | None = Query(None),
    q: Optional[str] = None
):

    if since is not None:
        try:
            datetime.datetime.fromisoformat(since.replace("Z", "+00:00"))
        except Exception:
            raise HTTPException(status_code=422, detail="since must be ISO-8601 UTC timestamp")
        
    with Session(engine) as session:
        stmt = select(messages)

        if from_msisdn:
            stmt = stmt.where(messages.from_msisdn == from_msisdn)
        if since:
            stmt = stmt.where(messages.ts >= since)
        if q:
            stmt = stmt.where(messages.text.ilike(f"%{q}%"))
        
        total = len(session.exec(stmt).all())
        stmt = stmt.order_by(messages.ts.asc(), messages.message_id.asc())
        stmt = stmt.offset(offset).limit(limit)
        data = session.exec(stmt).all()

        data_dicts = [m.model_dump(by_alias=True) for m in data]
        return {
            "data": data_dicts,
            "total": total,
            "limit": limit,
            "offset": offset
        }
    

@app.get("/stats")
def get_stats():
    with Session(engine) as session:
        # Total messages
        total_messages = session.exec(
            text("SELECT COUNT(*) FROM messages")
        ).one()[0]

        # Unique senders
        senders_count = session.exec(
            text("SELECT COUNT(DISTINCT from_msisdn) FROM messages")
        ).one()[0]

        # Messages per sender (top 10)
        mps = session.exec(
            text("""
                SELECT from_msisdn AS "from", COUNT(*) AS count
                FROM messages
                GROUP BY from_msisdn
                ORDER BY count DESC
                LIMIT 10
            """)
        ).all()
        messages_per_sender = [{"from": row[0], "count": row[1]} for row in mps]

        # First and last message timestamps
        first_ts = session.exec(
            text("SELECT ts FROM messages ORDER BY ts ASC LIMIT 1")
        ).first()
        last_ts = session.exec(
            text("SELECT ts FROM messages ORDER BY ts DESC LIMIT 1")
        ).first()

        return {
            "total_messages": total_messages,
            "senders_count": senders_count,
            "messages_per_sender": messages_per_sender,
            "first_message_ts": first_ts[0] if first_ts else None,
            "last_message_ts": last_ts[0] if last_ts else None,
        }