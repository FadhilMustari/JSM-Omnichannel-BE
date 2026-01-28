# API Endpoints (JSM-Omnichannel-BE)

This document lists all HTTP endpoints defined in the current codebase.

## Authentication & Access Notes
- There is no HTTP auth enforced in the FastAPI routes themselves.
- Admin routes read `request.state.admin` if present; otherwise they return a default admin context. This implies any admin auth is expected to be handled by upstream middleware/proxy that injects `request.state.admin`.
- Webhook endpoints require signature headers per platform (see Webhook section).

## Base
- Base URL: not defined in code (depends on deployment)
- Root: `GET /` returns `{ "message": "Omnichannel BE running" }`
Auth: none
Example:
```bash
curl -s http://localhost:8000/
```
Example response:
```json
{"message":"Omnichannel BE running"}
```

## Auth
### `GET /auth/verify`
- Purpose: Verify email by token.
Auth: none
- Query params:
  - `token` (string, required)
- Success response:
  - `{ "status": "success", "message": "Your email has been successfully verified." }`
- Errors:
  - `400` when token is invalid or expired.
Example:
```bash
curl -s "http://localhost:8000/auth/verify?token=YOUR_TOKEN"
```
Example response:
```json
{"status":"success","message":"Your email has been successfully verified."}
```

## Webhook
### `POST /webhook/{platform}`
- Purpose: Receive incoming messages from external platforms.
Auth: signature header required (per platform)
- Path params:
  - `platform` (string, required) — supported values are `telegram`, `line`, `whatsapp`.
- Request body:
  - Raw JSON payload as defined by the platform.
- Required headers (signature verification):
  - Telegram: `X-Telegram-Bot-Api-Secret-Token`
  - LINE: `X-Line-Signature`
  - WhatsApp: `X-Hub-Signature-256`
- Success response:
  - `{ "status": "ok" }`
- Errors:
  - `400` invalid platform or invalid JSON
  - `401` invalid signature
  - `429` rate limit exceeded
Example (Telegram):
```bash
curl -s -X POST "http://localhost:8000/webhook/telegram" \
  -H "Content-Type: application/json" \
  -H "X-Telegram-Bot-Api-Secret-Token: YOUR_SECRET" \
  -d '{"message":{"from":{"id":123},"text":"hello"}}'
```
Example response:
```json
{"status":"ok"}
```

## Admin (`/api/admin`)
### `GET /api/admin/me`
- Purpose: Return admin context attached to request.
Auth: expected via upstream middleware (not enforced here)
- Response:
  - `{ "id": string|null, "name": string|null, "role": "admin", "org_scope": "all" }` (defaults when no context)
Example:
```bash
curl -s http://localhost:8000/api/admin/me
```
Example response:
```json
{"id":null,"name":null,"role":"admin","org_scope":"all"}
```

### `GET /api/admin/conversations`
- Purpose: List conversations with last message and unread count.
Auth: expected via upstream middleware (not enforced here)
- Query params:
  - `q` (string, optional)
  - `organization_id` (string, optional)
  - `channel` (string, optional)
  - `unread_only` (bool, optional, default `false`)
  - `limit` (int, optional, default `20`)
  - `offset` (int, optional, default `0`)
Example:
```bash
curl -s "http://localhost:8000/api/admin/conversations?limit=10&offset=0"
```
Example response:
```json
[
  {
    "session_id":"SESSION_ID",
    "user_name":"Jane Doe",
    "user_email":"jane@example.com",
    "organization":{"id":"ORG_ID","name":"Acme"},
    "channel":"whatsapp",
    "last_message":{"text":"Hi","from":"user","created_at":"2024-01-01T00:00:00Z"},
    "unread_count":1,
    "updated_at":"2024-01-01T00:00:00Z"
  }
]
```

### `GET /api/admin/conversations/{session_id}`
- Purpose: Get conversation details.
Auth: expected via upstream middleware (not enforced here)
- Path params:
  - `session_id` (string, required)
Example:
```bash
curl -s "http://localhost:8000/api/admin/conversations/SESSION_ID"
```
Example response:
```json
{
  "session_id":"SESSION_ID",
  "user":{"id":"USER_ID","name":"Jane Doe","email":"jane@example.com"},
  "organization":{"id":"ORG_ID","name":"Acme"},
  "channel":"whatsapp",
  "created_at":"2024-01-01T00:00:00Z",
  "auth_status":"authenticated"
}
```

### `GET /api/admin/conversations/{session_id}/messages`
- Purpose: List conversation messages (marks session as read).
Auth: expected via upstream middleware (not enforced here)
- Path params:
  - `session_id` (string, required)
- Query params:
  - `limit` (int, optional, default `50`)
  - `offset` (int, optional, default `0`)
Example:
```bash
curl -s "http://localhost:8000/api/admin/conversations/SESSION_ID/messages?limit=50"
```
Example response:
```json
[
  {
    "message_id":"MSG_ID",
    "role":"user",
    "text":"Hello",
    "created_at":"2024-01-01T00:00:00Z",
    "platform_message_id":"PLATFORM_ID"
  }
]
```

### `POST /api/admin/conversations/{session_id}/messages`
- Purpose: Send an admin message to a conversation.
Auth: expected via upstream middleware (not enforced here)
- Path params:
  - `session_id` (string, required)
- Body (JSON):
  - `text` (string, required)
- Response:
  - `{ "status": "ok" }`
Example:
```bash
curl -s -X POST "http://localhost:8000/api/admin/conversations/SESSION_ID/messages" \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello from admin"}'
```
Example response:
```json
{"status":"ok"}
```

### `GET /api/admin/tickets`
- Purpose: List tickets linked to conversations (optionally filtered).
Auth: expected via upstream middleware (not enforced here)
- Query params:
  - `q` (string, optional)
  - `organization_id` (string, optional)
  - `channel` (string, optional)
  - `status` (string, optional, default `all`; supports `open`/`closed`)
  - `limit` (int, optional, default `20`)
  - `offset` (int, optional, default `0`)
Example:
```bash
curl -s "http://localhost:8000/api/admin/tickets?status=open&limit=10"
```
Example response:
```json
[
  {
    "ticket_key":"PROJ-123",
    "summary":"Issue summary",
    "status":"In Progress",
    "priority":"High",
    "channel":"whatsapp",
    "user":{"name":"Jane Doe","email":"jane@example.com"},
    "organization":{"id":"ORG_ID","name":"Acme"},
    "session_id":"SESSION_ID",
    "created_at":"2024-01-01T00:00:00Z",
    "updated_at":"2024-01-02T00:00:00Z"
  }
]
```

### `GET /api/admin/tickets/{ticket_key}`
- Purpose: Get ticket details plus linkage context.
Auth: expected via upstream middleware (not enforced here)
- Path params:
  - `ticket_key` (string, required)
Example:
```bash
curl -s "http://localhost:8000/api/admin/tickets/PROJ-123"
```
Example response:
```json
{
  "ticket_key":"PROJ-123",
  "summary":"Issue summary",
  "description":"Issue details",
  "status":"In Progress",
  "priority":"High",
  "assignee":"Agent Name",
  "reporter_email":"reporter@example.com",
  "organization":{"id":"ORG_ID","name":"Acme"},
  "channel":"whatsapp",
  "linked_session_id":"SESSION_ID",
  "jira_url":"https://jira.example.com/browse/PROJ-123",
  "created_at":"2024-01-01T00:00:00Z",
  "updated_at":"2024-01-02T00:00:00Z",
  "user":{"name":"Jane Doe","email":"jane@example.com"}
}
```

### `POST /api/admin/tickets/{ticket_key}/comment`
- Purpose: Add a comment to a ticket.
Auth: expected via upstream middleware (not enforced here)
- Path params:
  - `ticket_key` (string, required)
- Body (JSON):
  - `text` (string, required)
- Response:
  - `{ "status": "ok" }`
Example:
```bash
curl -s -X POST "http://localhost:8000/api/admin/tickets/PROJ-123/comment" \
  -H "Content-Type: application/json" \
  -d '{"text":"This is a test comment"}'
```
Example response:
```json
{"status":"ok"}
```

### `GET /api/admin/organizations`
- Purpose: List organizations with counts.
Auth: expected via upstream middleware (not enforced here)
- Query params:
  - `q` (string, optional)
Example:
```bash
curl -s "http://localhost:8000/api/admin/organizations?q=acme"
```
Example response:
```json
[
  {
    "organization_id":"ORG_ID",
    "name":"Acme",
    "domain":"acme.com",
    "user_count":10,
    "conversation_count":25,
    "ticket_count":5
  }
]
```

### `GET /api/admin/organizations/{organization_id}`
- Purpose: Get organization details, users, and stats.
Auth: expected via upstream middleware (not enforced here)
- Path params:
  - `organization_id` (string, required)
Example:
```bash
curl -s "http://localhost:8000/api/admin/organizations/ORG_ID"
```
Example response:
```json
{
  "organization_id":"ORG_ID",
  "name":"Acme",
  "domain":"acme.com",
  "users":[{"id":"USER_ID","name":"Jane Doe","email":"jane@example.com"}],
  "stats":{"conversations":25,"tickets":5}
}
```

### `POST /api/admin/organizations`
- Purpose: Create an organization.
Auth: expected via upstream middleware (not enforced here)
- Body (JSON):
  - `name` (string, required)
  - `domain` (string, required)
- Response:
  - `{ "organization_id": "<uuid>" }`
Example:
```bash
curl -s -X POST "http://localhost:8000/api/admin/organizations" \
  -H "Content-Type: application/json" \
  -d '{"name":"Acme Inc","domain":"acme.com"}'
```
Example response:
```json
{"organization_id":"ORG_ID"}
```

### `PATCH /api/admin/organizations/{organization_id}`
- Purpose: Update an organization.
Auth: expected via upstream middleware (not enforced here)
- Path params:
  - `organization_id` (string, required)
- Body (JSON):
  - `name` (string, optional)
  - `domain` (string, optional, cannot be empty string)
- Response:
  - `{ "status": "ok" }`
Example:
```bash
curl -s -X PATCH "http://localhost:8000/api/admin/organizations/ORG_ID" \
  -H "Content-Type: application/json" \
  -d '{"name":"Acme Updated"}'
```
Example response:
```json
{"status":"ok"}
```

### `POST /api/admin/conversations/{session_id}/link-ticket`
- Purpose: Link or update a ticket link for a conversation.
Auth: expected via upstream middleware (not enforced here)
- Path params:
  - `session_id` (string, required)
- Body (JSON):
  - `ticket_key` (string, required)
- Response:
  - `{ "status": "ok" }`
Example:
```bash
curl -s -X POST "http://localhost:8000/api/admin/conversations/SESSION_ID/link-ticket" \
  -H "Content-Type: application/json" \
  -d '{"ticket_key":"PROJ-123"}'
```
Example response:
```json
{"status":"ok"}
```

### `GET /api/admin/stats`
- Purpose: Summary counts.
Auth: expected via upstream middleware (not enforced here)
- Response:
  - `{ "total_conversations": int, "open_tickets": int, "active_organizations": int }`
Example:
```bash
curl -s http://localhost:8000/api/admin/stats
```
Example response:
```json
{"total_conversations":10,"open_tickets":3,"active_organizations":2}
```
