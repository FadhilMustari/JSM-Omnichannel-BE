from typing import Optional

from pydantic import BaseModel


class AdminMessageCreate(BaseModel):
    text: str


class AdminCommentCreate(BaseModel):
    text: str


class OrganizationCreate(BaseModel):
    jsm_id: str
    jsm_uuid: Optional[str] = None
    name: str
    is_active: Optional[bool] = True


class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    jsm_uuid: Optional[str] = None
    is_active: Optional[bool] = None
