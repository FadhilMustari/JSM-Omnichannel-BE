from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.database import get_db
from dependencies.services import get_auth_service
from services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])

@router.get("/verify")
def verify_email(token: str, auth_service: AuthService = Depends(get_auth_service), db: Session = Depends(get_db)):
    session, error = auth_service.verify_token(db, token)

    if error in {"user_not_found", "user_inactive"}:
        raise HTTPException(
            status_code=401,
            detail="User is not registered or inactive.",
        )
    if not session:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired verification token.",
        )

    db.commit()

    return {
        "status": "success",
        "message": "Your email has been successfully verified.",
    }
