"""Pydantic models for request/response validation."""
from pydantic import BaseModel
from typing import Optional


class LoginRequest(BaseModel):
    username: str
    password: str


class PlayerUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    sub_agent_id: Optional[int] = None
    credit_limit: Optional[float] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class PlayerCreate(BaseModel):
    account_id: str
    name: Optional[str] = ""
    phone: Optional[str] = ""
    sub_agent_id: Optional[int] = None
    credit_limit: Optional[float] = 0
    status: Optional[str] = "active"
    notes: Optional[str] = ""


class SubAgentUpdate(BaseModel):
    name: Optional[str] = None
    username: Optional[str] = None
    phone: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    telegram_username: Optional[str] = None
    venmo: Optional[str] = None
    credit_limit: Optional[float] = None
    status: Optional[str] = None
    vig_split: Optional[float] = None
    notes: Optional[str] = None


class SubAgentCreate(BaseModel):
    name: str
    username: Optional[str] = None
    phone: Optional[str] = ""
    telegram_chat_id: Optional[str] = ""
    telegram_username: Optional[str] = ""
    venmo: Optional[str] = ""
    credit_limit: Optional[float] = 0
    vig_split: Optional[float] = 0
    notes: Optional[str] = ""


class SettlementUpdate(BaseModel):
    status: Optional[str] = None
    payment_method: Optional[str] = None
    notes: Optional[str] = None


class SettingsUpdate(BaseModel):
    settings: dict


class ChangePassword(BaseModel):
    current_password: str
    new_password: str
