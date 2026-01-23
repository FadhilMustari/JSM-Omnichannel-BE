from sqlalchemy.orm import Session
from sqlalchemy import select
from models.models import ChannelSession
from datetime import datetime

class SessionService:

    def get_session_by_platform_user(self, db: Session, platform: str, external_user_id: str) -> ChannelSession | None:
        stmt = select(ChannelSession).where(
            ChannelSession.platform == platform,
            ChannelSession.external_user_id == external_user_id,
        )
        return db.scalar(stmt)

    def get_or_create_session(self, db: Session, platform: str, external_user_id: str) -> ChannelSession:
        session = self.get_session_by_platform_user(db, platform, external_user_id)
        if session:
            return session

        session = ChannelSession(
            platform=platform,
            external_user_id=external_user_id,
            auth_status="anonymous",
            status="active",
        )
        db.add(session)
        db.flush()  # penting, belum commit
        return session
