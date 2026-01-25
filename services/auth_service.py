import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from models.models import ChannelSession, EmailVerification, AuthStatus, User
from core.config import settings

class AuthService:
    TOKEN_EXP_MINUTES = 15

    def start_email_verification(self, db: Session, session: ChannelSession, email: str) -> str:
        """
        Start email verification flow:
        - create token
        - save verification record
        - set session.auth_status = pending_verification
        """
        token = str(uuid.uuid4())

        now_utc = datetime.now(timezone.utc)
        verification = EmailVerification(
            session_id=session.id,
            email=email,
            token=token,
            expires_at=now_utc + timedelta(minutes=self.TOKEN_EXP_MINUTES),
        )

        db.add(verification)

        session.auth_status = AuthStatus.pending.value
        db.add(session)

        return token

    def verify_token(self, db: Session, token: str) -> ChannelSession | None:
        """
        Verify email token and authenticate session
        """
        verification = (
            db.query(EmailVerification)
            .filter_by(token=token)
            .first()
        )

        if not verification:
            return None

        expires_at = verification.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            return None

        session = db.get(ChannelSession, verification.session_id)
        user = (
            db.query(User)
            .filter(User.email == verification.email)
            .first()
        )
        if not user:
            return None

        session.user_id = user.id
        session.auth_status = AuthStatus.authenticated.value

        db.delete(verification)
        db.add(session)

        return session
    
    def build_verify_link(self, token: str) -> str:
        return f"{settings.base_url}/auth/verify?token={token}"
