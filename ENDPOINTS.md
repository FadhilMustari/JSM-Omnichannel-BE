# JSM Omnichannel BE — API Endpoints

This document summarizes the available endpoints and the expected request/response payloads.

## Base

- `GET /healthz`
  - Response:
    ```json
    { "message": "Omnichannel BE running" }
    ```

---

## Webhooks

### `POST /webhook/{platform}`

`platform`: `telegram` | `whatsapp` | `line`

**Signature headers**

- Telegram: `X-Telegram-Bot-Api-Secret-Token`
- LINE: `X-Line-Signature`
- WhatsApp: `X-Hub-Signature-256`

**Request body**

- Raw webhook payload from each platform (original format).

**Response**

- `200` with:
  ```json
  { "status": "ok" }
  ```
- `204` if non‑text event
- `400/401/429` for invalid payload/signature/rate limit

---

### `POST /webhook/jira`

**Optional header**

- `X-Atlassian-Webhook-Secret` or `X-Jira-Webhook-Secret` (if configured)

**Request body (minimal shape)**

```json
{
  "webhookEvent": "comment_created",
  "issue": { "key": "SUPPORT-123" },
  "comment": {
    "author": {
      "displayName": "Agent Name",
      "emailAddress": "agent@company.com"
    },
    "body": "Comment text here"
  }
}
```

**Response**

- `200` with:
  ```json
  { "status": "ok" }
  ```
- `204` if event is not `comment_created`

---

## Auth

### `GET /auth/verify?token=...`

**Response**

```json
{ "status": "success", "message": "Your email has been successfully verified." }
```

**Errors**

- `400` if token invalid or expired

---

## API (prefix `/api`)

### `GET /api/me`

**Response**

```json
{ "id": null, "name": null, "role": "admin", "org_scope": "all" }
```
**Purpose**: Return admin context (id, name, role, org scope).

### `GET /api/conversations`

**Query params**
`q`, `organization_id`, `channel`, `unread_only`, `limit`, `offset`

**Response**: list of conversations with last message + unread count
**Purpose**: List conversations with filters and unread counts.

### `GET /api/conversations/{session_id}`

**Response**: conversation details
**Purpose**: Get a single conversation detail (user, org, channel, auth status).

### `GET /api/conversations/{session_id}/messages`

**Query params**: `limit`, `offset`  
**Response**: list of messages
**Purpose**: List messages for a conversation and mark as read.

### `POST /api/conversations/{session_id}/messages`

**Body**

```json
{ "text": "message text" }
```

**Response**

```json
{ "status": "ok" }
```
**Purpose**: Send an admin reply to the user and store it.

### `POST /api/conversations/{session_id}/link-ticket`

**Body**

```json
{ "ticket_key": "SUPPORT-123" }
```

**Response**

```json
{ "status": "ok", "ticket_key": "SUPPORT-123" }
```
**Purpose**: Link a conversation to a Jira ticket (create/update link).

### `GET /api/tickets`

**Query params**: `q`, `organization_id`, `channel`, `limit`, `offset`  
**Response**: list of tickets with Jira details
**Purpose**: List linked Jira tickets with live Jira data.

### `GET /api/tickets/{ticket_key}`

**Response**: ticket detail + `jira_url`
**Purpose**: Get a ticket detail from Jira for a specific key.

### `POST /api/tickets/{ticket_key}/comment`

**Body**

```json
{ "text": "comment text" }
```

**Response**

```json
{ "status": "ok" }
```
**Purpose**: Add a comment to a Jira ticket.

### `GET /api/organizations`

**Query params**: `q`, `limit`, `offset`  
**Response**: list of organizations + stats
**Purpose**: List organizations with conversation/ticket/user counts.

### `GET /api/organizations/{organization_id}`

**Response**: organization detail + stats
**Purpose**: Get organization detail and associated users/stats.

### `POST /api/organizations`

**Body**

```json
{ "jsm_id": "12", "jsm_uuid": "b0f2...", "name": "Tridorian", "is_active": true }
```

**Response**: created organization
**Purpose**: Create a new organization.

### `PATCH /api/organizations/{organization_id}`

**Body**

```json
{ "name": "Tridorian Updated", "is_active": false }
```

**Response**: updated organization
**Purpose**: Update organization attributes.

### `POST /api/sync/jsm`

**Response**

```json
{ "status": "ok", "result": { "organizations_seen": 0, "organizations_active": 0, "users_active": 0 } }
```
**Purpose**: Trigger a manual sync of JSM organizations and users.

### `GET /api/stats`

**Response**: global stats
**Purpose**: Get global counts of conversations, tickets, organizations.
