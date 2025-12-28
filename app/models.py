from dotenv import load_dotenv
load_dotenv()

from typing import Optional
from sqlmodel import Field, SQLModel, create_engine
from pydantic import ConfigDict
import os

class messages(SQLModel, table=True):
    __tablename__ = "messages"

    message_id: str = Field(primary_key=True)
    from_msisdn: str = Field(alias="from")
    to_msisdn: str = Field(alias="to")
    ts: str
    text: str | None = Field(default=None, max_length=4096)

    model_config = ConfigDict(
        serialize_by_alias=True
    )
 
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)