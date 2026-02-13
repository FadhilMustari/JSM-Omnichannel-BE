import logging
from typing import Any, Dict, List, Optional

import httpx
from core.config import settings
from core.http_client import get_async_client
from core.jira_constants import (
    PROJECT_KEY,
    PRIORITY_MAPPING,
    REQUEST_TYPE_ID,
    SERVICE_DESK_ID,
    START_DATE_FIELD,
)

logger = logging.getLogger(__name__)

class JiraService:
    def __init__(self):
        base_url, email, token, service_desk_id = settings.require_jira()
        self.base_url = base_url
        self.auth = (email, token)
        self.service_desk_id = service_desk_id

    def _headers(self) -> Dict[str, str]:
        return {"Accept": "application/json", "Content-Type": "application/json"}

    def _url(self, path: str) -> str:
        return f"{self.base_url.rstrip('/')}{path}"

    async def email_exists(self, email: str) -> bool:
        """
        Check if email exists as JSM customer in a service desk
        using Jira Service Management Experimental API.
        """
        url = self._url(
            f"/rest/servicedeskapi/servicedesk/{self.service_desk_id}/customer"
        )
        headers = {
            "Accept": "application/json",
            "X-ExperimentalApi": "opt-in",
        }
        params = {
            "query": email,
        }
        
        try:
            client = get_async_client()
            resp = await client.get(
                url,
                headers=headers,
                auth=self.auth,
                params=params,
                timeout=15.0,
            )
            if resp.status_code >= 400:
                logger.error(
                    "Jira customer check failed (%s): %s",
                    resp.status_code,
                    resp.text,
                )
                return False

            data = resp.json()
            customers = data.get("values", [])

            return any(
                (c.get("emailAddress") or "").lower() == email.lower()
                for c in customers
            )

        except httpx.RequestError:
            logger.exception("Failed to call Jira customer API")
            return False

    async def list_organizations(self, limit: int = 50) -> List[Dict[str, Any]]:
        url = self._url(
            f"/rest/servicedeskapi/servicedesk/{self.service_desk_id}/organization"
        )
        headers = {"Accept": "application/json"}
        start = 0
        results: List[Dict[str, Any]] = []
        client = get_async_client()

        while True:
            params = {"start": start, "limit": limit}
            try:
                resp = await client.get(
                    url,
                    headers=headers,
                    auth=self.auth,
                    params=params,
                    timeout=15.0,
                )
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPStatusError:
                logger.exception("Jira list_organizations failed: %s", resp.text)
                raise RuntimeError("Failed to list Jira organizations")
            except httpx.RequestError:
                logger.exception("Jira list_organizations request error")
                raise RuntimeError("Failed to list Jira organizations")

            values = data.get("values", [])
            results.extend(values)
            if data.get("isLastPage") is True:
                break
            start = int(data.get("start", start)) + int(data.get("limit", limit))
            if not values:
                break

        return results

    async def list_organization_users(
        self,
        organization_id: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        url = self._url(f"/rest/servicedeskapi/organization/{organization_id}/user")
        headers = {"Accept": "application/json"}
        start = 0
        results: List[Dict[str, Any]] = []
        client = get_async_client()

        while True:
            params = {"start": start, "limit": limit}
            try:
                resp = await client.get(
                    url,
                    headers=headers,
                    auth=self.auth,
                    params=params,
                    timeout=15.0,
                )
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPStatusError:
                logger.exception("Jira list_organization_users failed: %s", resp.text)
                raise RuntimeError("Failed to list Jira organization users")
            except httpx.RequestError:
                logger.exception("Jira list_organization_users request error")
                raise RuntimeError("Failed to list Jira organization users")

            values = data.get("values", [])
            results.extend(values)
            if data.get("isLastPage") is True:
                break
            start = int(data.get("start", start)) + int(data.get("limit", limit))
            if not values:
                break

        return results

    async def create_ticket(
        self,
        summary: str,
        description: str,
        priority_key: str,
        start_date: str,
        reporter_email: str,
        service_desk_id: str = SERVICE_DESK_ID,
        request_type_id: str = REQUEST_TYPE_ID,
    ) -> Dict[str, Any]:
        priority_id = PRIORITY_MAPPING.get(priority_key.upper())
        if not priority_id:
            raise ValueError(f"Unsupported priority: {priority_key}")

        payload = {
            "serviceDeskId": service_desk_id,
            "requestTypeId": request_type_id,
            "requestFieldValues": {
                "summary": summary,
                "description": description,
                "priority": {"id": priority_id},
                START_DATE_FIELD: start_date,
            },
            "raiseOnBehalfOf": reporter_email,
        }

        url = self._url("/rest/servicedeskapi/request")
        client = get_async_client()
        try:
            resp = await client.post(
                url,
                json=payload,
                headers=self._headers(),
                auth=self.auth,
                timeout=15.0,
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "issue_id": data.get("issueId"),
                "issue_key": data.get("issueKey"),
                "request_id": data.get("requestId"),
            }
        except httpx.HTTPStatusError:
            logger.exception("Jira create_ticket failed: %s", resp.text)
            raise RuntimeError("Failed to create Jira ticket")
        except httpx.RequestError:
            logger.exception("Jira create_ticket request error")
            raise RuntimeError("Failed to create Jira ticket")

    async def get_ticket_detail(self, ticket_key: str) -> Dict[str, Any]:
        url = self._url(f"/rest/api/3/issue/{ticket_key}")
        params = {"fields": "summary,description,status,assignee,priority,reporter,created,updated"}
        client = get_async_client()
        try:
            resp = await client.get(
                url,
                headers=self._headers(),
                auth=self.auth,
                params=params,
                timeout=15.0,
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError:
            logger.exception("Jira get_ticket_detail failed: %s", resp.text)
            raise RuntimeError("Failed to fetch Jira ticket")
        except httpx.RequestError:
            logger.exception("Jira get_ticket_detail request error")
            raise RuntimeError("Failed to fetch Jira ticket")

        fields = data.get("fields", {})
        assignee = fields.get("assignee") or {}
        priority = fields.get("priority") or {}
        status = fields.get("status") or {}
        reporter = fields.get("reporter") or {}
        return {
            "ticket_key": data.get("key"),
            "summary": fields.get("summary"),
            "description": fields.get("description"),
            "status": status.get("name"),
            "assignee": assignee.get("displayName"),
            "priority": priority.get("name"),
            "reporter_email": reporter.get("emailAddress"),
            "created_at": fields.get("created"),
            "updated_at": fields.get("updated"),
        }

    async def list_tickets_by_reporter(
        self,
        email: str,
        project: str = PROJECT_KEY,
        status_filter: str = "all",
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        jql = f'project = {project} AND reporter = "{email}"'
        if status_filter == "open":
            jql += " AND statusCategory != Done"
        elif status_filter == "closed":
            jql += " AND statusCategory = Done"
        url = self._url("/rest/api/3/search/jql")
        payload = {
            "jql": jql,
            "fields": ["summary", "status", "assignee", "priority", "created"],
            "maxResults": max_results,
        }
        client = get_async_client()
        try:
            resp = await client.post(
                url,
                headers=self._headers(),
                auth=self.auth,
                json=payload,
                timeout=15.0,
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError:
            logger.exception("Jira list_tickets_by_reporter failed: %s", resp.text)
            raise RuntimeError("Failed to list Jira tickets")
        except httpx.RequestError:
            logger.exception("Jira list_tickets_by_reporter request error")
            raise RuntimeError("Failed to list Jira tickets")

        issues = data.get("issues", [])
        results: List[Dict[str, Any]] = []
        for issue in issues:
            fields = issue.get("fields", {})
            assignee = fields.get("assignee") or {}
            priority = fields.get("priority") or {}
            status = fields.get("status") or {}
            results.append(
                {
                    "ticket_key": issue.get("key"),
                    "summary": fields.get("summary"),
                    "status": status.get("name"),
                    "assignee": assignee.get("displayName"),
                    "priority": priority.get("name"),
                    "created_at": fields.get("created"),
                }
            )
        return results

    async def get_issues_by_keys(self, ticket_keys: list[str]) -> List[Dict[str, Any]]:
        if not ticket_keys:
            return []
        keys = ",".join(ticket_keys)
        jql = f"key in ({keys})"
        url = self._url("/rest/api/3/search/jql")
        payload = {
            "jql": jql,
            "fields": ["summary", "status", "assignee", "priority", "reporter", "created", "updated"],
            "maxResults": len(ticket_keys),
        }
        client = get_async_client()
        try:
            resp = await client.post(
                url,
                headers=self._headers(),
                auth=self.auth,
                json=payload,
                timeout=15.0,
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError:
            logger.exception("Jira get_issues_by_keys failed: %s", resp.text)
            raise RuntimeError("Failed to fetch Jira tickets")
        except httpx.RequestError:
            logger.exception("Jira get_issues_by_keys request error")
            raise RuntimeError("Failed to fetch Jira tickets")

        issues = data.get("issues", [])
        results: List[Dict[str, Any]] = []
        for issue in issues:
            fields = issue.get("fields", {})
            assignee = fields.get("assignee") or {}
            priority = fields.get("priority") or {}
            status = fields.get("status") or {}
            reporter = fields.get("reporter") or {}
            results.append(
                {
                    "ticket_key": issue.get("key"),
                    "summary": fields.get("summary"),
                    "status": status.get("name"),
                    "assignee": assignee.get("displayName"),
                    "priority": priority.get("name"),
                    "reporter_email": reporter.get("emailAddress"),
                    "created_at": fields.get("created"),
                    "updated_at": fields.get("updated"),
                }
            )
        return results

    async def list_all_tickets(
        self,
        project: str = PROJECT_KEY,
        start_at: int = 0,
        max_results: int = 100,
    ) -> Dict[str, Any]:
        jql = f"project = {project} ORDER BY created ASC"
        url = self._url("/rest/api/3/search/jql")
        payload = {
            "jql": jql,
            "fields": [
                "summary",
                "description",
                "status",
                "assignee",
                "priority",
                "reporter",
                "created",
                "updated",
            ],
            "startAt": start_at,
            "maxResults": max_results,
        }
        client = get_async_client()
        try:
            resp = await client.post(
                url,
                headers=self._headers(),
                auth=self.auth,
                json=payload,
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError:
            logger.exception("Jira list_all_tickets failed: %s", resp.text)
            raise RuntimeError("Failed to list Jira tickets")
        except httpx.RequestError:
            logger.exception("Jira list_all_tickets request error")
            raise RuntimeError("Failed to list Jira tickets")

        return {
            "issues": data.get("issues", []),
            "total": data.get("total", 0),
            "startAt": data.get("startAt", start_at),
            "maxResults": data.get("maxResults", max_results),
        }

    async def add_comment(
        self,
        ticket_key: str,
        comment: str,
        author: Optional[Dict[str, str]] = None,
    ) -> None:
        header = ""
        if author:
            name = author.get("name") or "Unknown"
            email = author.get("email") or "unknown@example.com"
            header = f"From: {name} <{email}>\n\n"

        payload = {"body": f"{header}{comment}", "public": True}
        url = self._url(f"/rest/servicedeskapi/request/{ticket_key}/comment")
        client = get_async_client()
        try:
            resp = await client.post(
                url,
                headers=self._headers(),
                auth=self.auth,
                json=payload,
                timeout=15.0,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError:
            logger.exception("Jira add_comment failed: %s", resp.text)
            raise RuntimeError("Failed to add Jira comment")
        except httpx.RequestError:
            logger.exception("Jira add_comment request error")
            raise RuntimeError("Failed to add Jira comment")

    async def get_public_comments(
        self,
        ticket_key: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        url = self._url(f"/rest/servicedeskapi/request/{ticket_key}/comment")
        params = {"limit": limit, "public": True}
        client = get_async_client()
        try:
            resp = await client.get(
                url,
                headers=self._headers(),
                auth=self.auth,
                params=params,
                timeout=15.0,
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError:
            logger.exception("Jira get_public_comments failed: %s", resp.text)
            raise RuntimeError("Failed to fetch Jira comments")
        except httpx.RequestError:
            logger.exception("Jira get_public_comments request error")
            raise RuntimeError("Failed to fetch Jira comments")

        comments = data.get("values", [])
        results: List[Dict[str, Any]] = []
        for comment in comments:
            author = comment.get("author") or {}
            results.append(
                {
                    "body": comment.get("body"),
                    "created_at": comment.get("created"),
                    "author": author.get("displayName"),
                    "public": comment.get("public"),
                }
            )
        return results
