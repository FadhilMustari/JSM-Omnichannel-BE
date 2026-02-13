import json
import logging
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql import func

from core.jira_constants import PROJECT_KEY
from models.models import JiraTicket, Organization, User
from services.jira_service import JiraService


class JiraSyncService:
    def __init__(self, jira_service: JiraService) -> None:
        self.jira_service = jira_service
        self.logger = logging.getLogger(__name__)

    async def sync_jira_organizations_and_users(self, db: Session) -> dict[str, Any]:
        self.logger.info("JSM sync started")

        # Step 1: Fetch organizations from JSM.
        organizations = await self.jira_service.list_organizations()
        self.logger.info("JSM organizations fetched", extra={"count": len(organizations)})

        # Step 2: Upsert organizations by jsm_id.
        org_jsm_ids: set[str] = set()
        for org in organizations:
            jsm_id = str(org.get("id") or "").strip()
            if not jsm_id:
                continue
            jsm_uuid = org.get("uuid")
            name = org.get("name") or "-"
            org_jsm_ids.add(jsm_id)

            stmt = insert(Organization).values(
                jsm_id=jsm_id,
                jsm_uuid=jsm_uuid,
                name=name,
                is_active=True,
            )
            update = {
                "jsm_uuid": stmt.excluded.jsm_uuid,
                "name": stmt.excluded.name,
                "is_active": True,
                "updated_at": func.now(),
            }
            db.execute(stmt.on_conflict_do_update(index_elements=["jsm_id"], set_=update))

        # Step 3: Deactivate organizations no longer in JSM.
        if org_jsm_ids:
            db.query(Organization).filter(~Organization.jsm_id.in_(org_jsm_ids)).update(
                {"is_active": False, "updated_at": func.now()},
                synchronize_session=False,
            )
        else:
            db.query(Organization).update(
                {"is_active": False, "updated_at": func.now()},
                synchronize_session=False,
            )

        db.flush()

        org_rows = db.query(Organization.id, Organization.jsm_id).all()
        org_id_map = {row.jsm_id: row.id for row in org_rows if row.jsm_id}

        # Step 4: Fetch and upsert users for each organization.
        user_account_ids: set[str] = set()
        for org in organizations:
            jsm_id = str(org.get("id") or "").strip()
            if not jsm_id:
                continue
            org_id = org_id_map.get(jsm_id)
            if not org_id:
                continue

            members = await self.jira_service.list_organization_users(jsm_id)
            self.logger.info(
                "JSM organization users fetched",
                extra={"org_id": jsm_id, "count": len(members)},
            )
            for member in members:
                account_id = (member.get("accountId") or "").strip()
                email = (member.get("emailAddress") or "").strip().lower()
                if not account_id or not email:
                    continue
                user_account_ids.add(account_id)

                stmt = insert(User).values(
                    jsm_account_id=account_id,
                    email=email,
                    organization_id=org_id,
                    is_active=True,
                )
                update = {
                    "email": stmt.excluded.email,
                    "organization_id": stmt.excluded.organization_id,
                    "is_active": True,
                    "updated_at": func.now(),
                }
                db.execute(
                    stmt.on_conflict_do_update(
                        index_elements=["jsm_account_id"],
                        set_=update,
                    )
                )

        # Step 5: Deactivate users no longer in JSM.
        if user_account_ids:
            db.query(User).filter(~User.jsm_account_id.in_(user_account_ids)).update(
                {"is_active": False, "updated_at": func.now()},
                synchronize_session=False,
            )
        else:
            db.query(User).update(
                {"is_active": False, "updated_at": func.now()},
                synchronize_session=False,
            )

        db.commit()

        summary = {
            "organizations_seen": len(organizations),
            "organizations_active": len(org_jsm_ids),
            "users_active": len(user_account_ids),
        }
        self.logger.info("JSM sync completed", extra=summary)
        return summary

    async def sync_jira_tickets(self, db: Session, project_key: str = PROJECT_KEY) -> dict[str, Any]:
        self.logger.info("Jira ticket sync started", extra={"project_key": project_key})

        start_at = 0
        max_results = 100
        total_seen = 0
        while True:
            page = await self.jira_service.list_all_tickets(
                project=project_key,
                start_at=start_at,
                max_results=max_results,
            )
            issues = page.get("issues", [])
            total = int(page.get("total") or 0)
            if not issues:
                break

            for issue in issues:
                ticket_key = issue.get("key")
                if not ticket_key:
                    continue
                fields = issue.get("fields", {}) or {}
                assignee = fields.get("assignee") or {}
                priority = fields.get("priority") or {}
                status = fields.get("status") or {}
                reporter = fields.get("reporter") or {}
                description = fields.get("description")
                if description is not None and not isinstance(description, str):
                    description = json.dumps(description, ensure_ascii=True)

                stmt = insert(JiraTicket).values(
                    ticket_key=ticket_key,
                    project_key=project_key,
                    summary=fields.get("summary"),
                    description=description,
                    status=status.get("name"),
                    priority=priority.get("name"),
                    assignee=assignee.get("displayName"),
                    reporter_email=reporter.get("emailAddress"),
                    created_at=fields.get("created"),
                    updated_at=fields.get("updated"),
                )
                update = {
                    "project_key": stmt.excluded.project_key,
                    "summary": stmt.excluded.summary,
                    "description": stmt.excluded.description,
                    "status": stmt.excluded.status,
                    "priority": stmt.excluded.priority,
                    "assignee": stmt.excluded.assignee,
                    "reporter_email": stmt.excluded.reporter_email,
                    "created_at": stmt.excluded.created_at,
                    "updated_at": stmt.excluded.updated_at,
                    "last_synced_at": func.now(),
                }
                db.execute(
                    stmt.on_conflict_do_update(
                        index_elements=["ticket_key"],
                        set_=update,
                    )
                )

            total_seen += len(issues)
            start_at = int(page.get("startAt", start_at)) + int(page.get("maxResults", max_results))
            if start_at >= total:
                break

        db.commit()
        summary = {"tickets_seen": total_seen, "project_key": project_key}
        self.logger.info("Jira ticket sync completed", extra=summary)
        return summary
