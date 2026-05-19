# NimbusCloud REST API Reference

## Authentication

All API requests require a bearer token in the `Authorization` header:

```
Authorization: Bearer ncp_live_abc123...
```

Tokens are created from Settings → API → "Create token" on the web app. Each token has a scope (`read`, `write`, or `admin`) and an optional expiry date. We recommend creating scoped tokens with the minimum permissions your application needs and setting an expiry of no more than 90 days.

Token format: `ncp_live_` prefix for production, `ncp_test_` for sandbox. Tokens are 40 characters after the prefix, base58-encoded.

## Rate limits

Rate limits vary by plan:

- **Free** — 60 requests per minute, no concurrency limit
- **Pro** — 600 requests per minute, 4 concurrent uploads
- **Business** — 6,000 requests per minute, 16 concurrent uploads
- **Enterprise** — Negotiated custom limits, typically 60,000 rpm

Rate limits are applied per-token, not per-account. Exceeding the limit returns `HTTP 429 Too Many Requests` with a `Retry-After` header indicating the number of seconds to wait.

## Common error responses

- **401 Unauthorized** — Missing or malformed `Authorization` header. Token may be truncated; verify full 40-char body.
- **403 Forbidden** — Token is valid but lacks the required scope. Check token scope in Settings → API.
- **404 Not Found** — The resource does not exist, or your token cannot see it.
- **409 Conflict** — You attempted to create a resource that already exists.
- **429 Too Many Requests** — Rate limit exceeded. Honor the `Retry-After` header.
- **507 Insufficient Storage** — Your account has hit its quota. Upload aborted; no partial data is stored.

## Common API issue: "403 on /v1/uploads despite a valid token"

Every week we see this. The customer has a token that works on `GET /v1/files/*` but fails with 403 on `POST /v1/uploads`. The cause is nearly always that the token has `read` scope, not `write`. Read-scoped tokens can retrieve file metadata and download URLs but cannot initiate uploads. Resolution: create a new token with `write` scope and rotate.
