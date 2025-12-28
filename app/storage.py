from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel import SQLModel, Session, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from datetime import datetime, timezone
from typing import Optional
from .models import messages
import logging

logger = logging.getLogger("uvicorn.error")

def insert_message(session: Session, payload) -> str:
	try:
		statement = select(messages).where(messages.message_id == payload.message_id)
		existing_message = session.exec(statement).first()

		if existing_message:
			return "duplicate"

		msg = messages(
			message_id=payload.message_id,
			from_msisdn=payload.from_msisdn,
			to_msisdn=payload.to_msisdn,
			ts=payload.ts,
			text=payload.text
		)

		session.add(msg)
		session.commit()
		return "created"
	except (IntegrityError, SQLAlchemyError) as e:
		logger.error(f"policy issue: {e}")
		session.rollback()

