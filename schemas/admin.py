from typing import Optional

from pydantic import BaseModel


class AdminMessageCreate(BaseModel):
    text: str


class AdminCommentCreate(BaseModel):
    text: str


class OrganizationCreate(BaseModel):
    name: str
    domain: str


class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    domain: Optional[str] = None
