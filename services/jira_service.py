import logging
import httpx
from core.config import settings
from core.http_client import get_async_client

logger = logging.getLogger(__name__)

class JiraService:
    def __init__(self):
        self.base_url = settings.jira_base
        self.auth = (settings.jira_email, settings.jira_token)
        self.service_desk_id = settings.jira_service_desk_id

    async def email_exists(self, email: str) -> bool:
        """
        Check if email exists as JSM customer in a service desk
        using Jira Service Management Experimental API.
        """
        url = (f"{self.base_url}/rest/servicedeskapi/servicedesk/{self.service_desk_id}/customer")
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
