# Beauty Studio

Full-stack website for a beauty parlour.

| Layer     | Technology                |
| --------- | ------------------------- |
| Frontend  | React 19 + Vite 8 + TS 6  |
| Backend   | Python + FastAPI          |
| Database  | MongoDB (async driver)    |
| Storage   | AWS S3                    |
| Auth      | JWT in an HttpOnly cookie |
| Email     | SMTP                      |

**Status: backend domain, admin authentication and S3 media management are in
place.** Every `/api/v1/admin` route requires a session, password reset works
end to end, and images can be uploaded to S3 through the API. There is still no
admin UI and the frontend only shows the foundation shell.

## Layout

```
.
├── backend/
│   ├── app/
│   │   ├── main.py            FastAPI app factory, CORS, lifespan
│   │   ├── core/              settings, logging, errors, argon2, JWT, cookies,
│   │   │                      media validation + object-key generation
│   │   ├── api/
│   │   │   ├── deps.py        dependency chain (get_database is the test seam)
│   │   │   ├── deps_auth.py   session resolution + CSRF check
│   │   │   └── v1/routes/
│   │   │       ├── health.py
│   │   │       ├── auth.py    login, logout, me, password reset
│   │   │       ├── public/    read-only + review submission
│   │   │       └── admin/     CRUD (session required), incl. media uploads
│   │   ├── cli/               create_admin: the only account-provisioning path
│   │   ├── db/                MongoDB client factory + index management
│   │   ├── storage/           S3 client factory + S3StorageService
│   │   ├── repositories/      MongoDB queries
│   │   ├── services/          business rules, mail delivery, media coordination
│   │   ├── schemas/           Pydantic request/response schemas
│   │   └── models/            MongoDB document models
│   ├── tests/
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   └── .env.development.example  local-http cookie overrides
├── frontend/
│   └── src/
│       ├── lib/               env + typed API client
│       ├── types/             shared API types
│       └── App.tsx            foundation shell
├── .env                       git-ignored, real credentials
├── .env.example               template, safe to commit
└── .venv                      git-ignored Python environment
```

## Data model

Six collections: `admins`, `site_settings`, `services`, `gallery`,
`testimonials`, `offers`. Only indexes the application actually queries are
created at start-up, and a failure to create one never blocks start-up.

Notable invariants, all enforced server-side:

- **Money** is a `Decimal` end to end, stored as BSON `Decimal128` and rendered
  as a JSON string (`"49.99"`) so no float rounding is ever introduced.
- **`site_settings` is a singleton**, guaranteed by a unique index on
  `singleton_key` plus an atomic upsert. It is seeded from `APP_NAME` on first
  read, so the public endpoint works on a fresh install with no seed script.
- **A submitted testimonial is always `pending` and invisible.** The public
  submission schema has no moderation fields, and the public feed filters on
  `status=approved AND is_visible=true`. Publishing requires the moderation
  endpoint; asking for `is_visible=true` with a non-approved status is a `409`.
- **Inactive content is reported as `404`, not `403`**, so the public API never
  reveals items the business has switched off.
- **Opening hours are `HH:MM` strings.** BSON has no time-of-day type, so
  storing `datetime.time` would fail to encode.
- **Every timestamp is timezone-aware UTC.** Naive values are normalised to UTC
  at the model boundary, which keeps aware/naive comparisons from failing.

## API

Base paths: `/api/v1/public` (visitor-facing), `/api/v1/admin` (management, session
required) and `/api/v1/auth`. Health stays at `/api/health`. Interactive docs at
`/docs`.

| Method + path | Notes |
| --- | --- |
| `GET /api/health` | liveness probe, unauthenticated |
| `GET /api/v1/public/site-settings` | singleton, auto-seeded |
| `GET /api/v1/public/services` | active only, ordered by `display_order` |
| `GET /api/v1/public/services/{id}` | `404` when inactive |
| `GET /api/v1/public/gallery` | active only, **never** exposes `s3_key` |
| `GET /api/v1/public/gallery/{id}` | `404` when inactive |
| `GET /api/v1/public/offers` | active only, ordered |
| `GET /api/v1/public/offers/{id}` | `404` when inactive |
| `GET /api/v1/public/testimonials` | approved **and** visible only |
| `POST /api/v1/public/testimonials` | submit; always pending + hidden |
| `GET /api/v1/public/testimonials/{id}` | `404` unless public |

Admin CRUD follows the same shape for each of `site-settings`, `services`,
`gallery`, `offers` and `testimonials`:

| Method + path | Notes |
| --- | --- |
| `GET`, `POST` `/api/v1/admin/{resource}` | list (paged) / create |
| `GET`, `PATCH`, `DELETE` `/api/v1/admin/{resource}/{id}` | read / partial update / delete |
| `PATCH /api/v1/admin/{resource}/{id}/active` | activate or deactivate |
| `PUT /api/v1/admin/{resource}/order` | bulk `display_order` reorder |
| `GET`, `PUT`, `PATCH` `/api/v1/admin/site-settings` | singleton replace/patch |
| `PATCH /api/v1/admin/testimonials/{id}/moderate` | approve / reject / publish |

List endpoints share one envelope: `{ "items": [...], "total": n, "skip": s,
"limit": l }`, with `skip` 0–10000 and `limit` 1–200 (default 50).

Every one of the 33 admin operations requires a session, and the requirement is
declared once on the router rather than in each handler, so a newly added admin
route is protected by construction. `tests/test_auth.py` walks the real route
table with no session and asserts each one answers `401`.

### Media (S3)

| Method + path | Notes |
| --- | --- |
| `POST /api/v1/admin/media` | `multipart/form-data`; validates, uploads, records |
| `PATCH /api/v1/admin/media/{id}` | metadata only; no re-upload needed |
| `DELETE /api/v1/admin/media/{id}` | removes the object, then the record |

`POST` takes the file as `file` plus optional `title` (required), `description`,
`category`, `is_active` and `display_order` form fields.

```bash
curl -X POST https://api.example.com/api/v1/admin/media \
  -b cookies.txt -H "X-CSRF-Token: $TOKEN" \
  -F file=@bridal.jpg -F title="Bridal" -F category=gallery
```

**Storage service.** `S3StorageService` (`app/storage/s3.py`) is the only code
that calls boto3. It exposes `upload`, `delete`, `exists` and `public_url`, and
translates every botocore failure into a fixed-message application error. It
knows nothing about FastAPI, so routes and services depend on the class rather
than on boto3. Because boto3 is synchronous, each call runs in a worker thread
so a multi-megabyte upload cannot stall the event loop.

**Object keys** are `media/{category}/{uuid4}.{extension}` with `category` drawn
from a closed set (`logo`, `gallery`, `service`, `offer`, `general`). The
user-supplied filename is never part of the key — only the sanitised original
name is kept on the record, for display. Every key is re-validated against that
shape immediately before each S3 call, so a tampered document cannot be turned
into a delete against an arbitrary object.

**Validation** is by file signature, not by extension or the declared
`Content-Type`. JPEG, PNG and WebP are accepted. SVG, HTML, XML, executables,
shebang scripts, PDFs and archives are refused with a pointed message, and a
declared type that disagrees with the actual bytes is rejected. The `Content-Type`
written to S3 comes from the sniffed type, so a `.svg` filename carrying PNG data
is stored as a PNG. The size ceiling is `PRODUCT_IMAGE_MAX_BYTES`, applied while
the body is still being read.

**Partial failures are never reported as success.** An upload writes S3 first
and MongoDB second, so if the insert fails the object is deleted before the error
is returned; if that cleanup also fails, the *database* error is still what the
client sees and the stranded object is logged for an operator. A delete removes
the object first and the record second — if the S3 delete is denied the request
fails with `502 storage_access_denied` and the record is kept, so the failure is
visible and retryable.

**Metadata updates cannot repoint a record.** `PATCH /media/{id}` accepts only
`title`, `description`, `category`, `is_active` and `display_order`; `s3_key`,
`image_url`, `content_type` and `file_size` are rejected with `422`.

**Limits (Phase 1).** URLs point at the bucket's own virtual-hosted endpoint, so
the bucket policy must allow public reads for images to be viewable; there is no
CDN and no signed URLs. `S3StorageService.public_url` is the single place a CDN
base would be substituted later. There is no `STORAGE_MODE=local` backend, and no
image resizing, cropping or derivative generation. Validation classifies by header
and does not decode the image, so a truncated file with a valid signature is
accepted. Video is not supported.

### Authentication

| Method + path | Auth | Notes |
| --- | --- | --- |
| `POST /api/v1/auth/login` | none | throttled; sets the session + CSRF cookies |
| `GET /api/v1/auth/me` | session | the current admin profile |
| `POST /api/v1/auth/logout` | session | clears both cookies |
| `POST /api/v1/auth/forgot-password` | none | throttled; always `202` |
| `POST /api/v1/auth/reset-password` | emailed token | single-use, short-lived |

How it works, and why:

- **The access token is an `HttpOnly` cookie**, never a `localStorage` entry, so
  an XSS payload cannot read it. The body of a successful login returns the
  profile and the CSRF token, but not the access token.
- **CSRF protection is mandatory**, because the production configuration uses
  `SameSite=none` (needed when the API and frontend are on different sites),
  which removes the browser's own protection. Session cookies are therefore
  double-submit: state-changing requests must echo the `X-CSRF-Token` header,
  compared against the CSRF cookie in constant time. A pure
  `Authorization: Bearer` request is exempt, since it is not a browser form post
  and cannot be forged cross-site. The check is enforced under every cookie
  policy, so behaviour is identical in every environment.
- **Passwords are hashed with Argon2id** (64 MiB, 3 passes) at the OWASP
  baseline. Parameters are embedded in each digest, so they can be raised later
  without a migration.
- **No default account exists.** An initial admin is created deliberately:
  `python -m app.cli.create_admin`. The password is read from a hidden prompt
  (or `--password-stdin`) and is deliberately *not* accepted as a command-line
  argument, because an argument lands in shell history and in `ps`.
- **Account enumeration is treated as a security property**, not a nicety. A
  wrong password, an unknown address, a disabled account and a mail-delivery
  failure all produce byte-identical responses. This has caught real bugs: an
  unset `FRONTEND_URL` once made a *known* address answer `503` while an unknown
  one answered `202`.
- **Login is throttled** on both the client IP and the submitted address, and a
  successful login clears the counter. `X-Forwarded-For` is deliberately ignored
  because it is attacker-controlled without a trusted proxy in front.

#### Known limitations

Stated plainly rather than glossed over:

- **Logout is browser-side only.** The token is stateless and is not on a
  denylist, so a copy captured before logout stays valid until it expires. The
  `jti` claim is issued for a future denylist, and the short token lifetime is
  what bounds the exposure. Deactivating an admin *does* revoke access
  immediately, because the account is re-checked on every request.
- **The rate limiter is per process, in memory.** Correct for the current
  single-instance deployment; with N workers the effective limit becomes N ×
  `LOGIN_RATE_LIMIT_MAX`. A shared store is required before scaling out.
- **Rate limiting is in place for login and forgot-password**, not for
  `reset-password` (the 256-bit token is not guessable) or for admin writes
  (protected by the session).

### Errors

Every failure uses one shape, including framework-generated 404/405:

```json
{ "error": { "code": "not_found", "message": "..." } }
```

`400 bad_request` malformed id · `401 not_authenticated` / `invalid_credentials` ·
`403 csrf_failed` · `404 not_found` · `405 method_not_allowed` · `409 conflict` ·
`422 validation_error` (with per-field `details`) · `429 rate_limited` (with
`Retry-After`) · `500 database_error` / `internal_error`.

Validation details report `location`, `message` and `type` but never the
rejected value, and no handler forwards a traceback, driver message or
configuration value.

## Setup

```bash
# 1. Environment file (already exists - edit if needed)
#    Linux/macOS: cp .env.example .env
#    Windows:     Copy-Item .env.example .env
#
#    Generate a signing secret and put it in JWT_SECRET:
#    python -c "import secrets; print(secrets.token_urlsafe(64))"

# 2. Backend
python -m venv .venv
.venv\Scripts\python -m pip install -r backend/requirements.txt -r backend/requirements-dev.txt

# 3. Frontend
cd frontend && npm install
```

## Run

Backend (from the repository root):

```bash
.venv\Scripts\python -m uvicorn app.main:app --reload --app-dir backend --port 8000
```

Frontend:

```bash
cd frontend
npm run dev      # http://127.0.0.1:5173
```

Health check: <http://127.0.0.1:8000/api/health> · Docs: <http://127.0.0.1:8000/docs>

The interactive docs and `/openapi.json` are served only when `DEBUG=true`. With
`DEBUG=false` - the production setting - all three paths return `404`, because
they describe every admin endpoint and are of no use to a visitor.

The Vite dev server proxies `/api` to `http://127.0.0.1:8000`, so the browser
stays on a single origin during development. `npm run preview` uses the same
`DEV_API_TARGET`, so the production build can be exercised against a local
backend before it is deployed.

### Creating the first admin

There is no default account and no seeding step. Create one explicitly:

```bash
cd backend
..\.venv\Scripts\python -m app.cli.create_admin
```

It prompts for the address, display name and password (typed twice, not echoed).
For automation, supply the password via a variable so it never reaches the shell
history or the process list:

```bash
ADMIN_INITIAL_PASSWORD='...' ..\.venv\Scripts\python -m app.cli.create_admin \
  --email you@example.com --name "Your Name" --password-stdin
```

Re-running it reports that the address is taken and changes nothing, so it can
never quietly reset an existing password.

## Production

Two processes behind one HTTPS origin. No container, orchestrator or CDN is
required or assumed.

**1. Build the frontend once** and serve `frontend/dist/` as static files:

```bash
cd frontend && npm ci && npm run build
```

**2. Run the backend** without the reload watcher:

```bash
.venv\Scripts\python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

**3. Route both from the same origin**, which is what keeps the session cookie
and CORS simple. `/api` goes to Uvicorn, everything else to `frontend/dist/`:

```
/api/*          ->  http://127.0.0.1:8000
/*              ->  frontend/dist/   (static)
```

Because the two are same-origin, `CORS_ORIGINS` is not exercised in this
arrangement. It only needs changing if the API is moved to its own domain, in
which case the API origin must be listed there *and* the frontend's
`VITE_API_BASE_URL` set to an absolute URL at build time.

Before the first request can succeed, three values must be set in `.env`:

- `JWT_SECRET` - at least 32 characters. Until it is, every protected endpoint
  rejects the request and the login route cannot mint a session.
- `FRONTEND_URL` - the public HTTPS origin. Password-reset links are built from
  it, and a reset email cannot be produced without it.
- `CORS_ORIGINS` - only if the API is cross-origin.

Then create the first admin (there is no default account):

```bash
cd backend && ..\.venv\Scripts\python -m app.cli.create_admin
```

## Checks

```bash
# Backend
.venv\Scripts\python -m ruff check backend
.venv\Scripts\python -m ruff format --check backend
cd backend && ..\.venv\Scripts\python -m pytest

# Frontend
cd frontend && npm run lint && npm run typecheck && npm run build
```

The backend suite is fully offline: `tests/conftest.py` points `MONGO_URI` at an
unreachable local port and serves every request from an in-memory MongoDB
(`mongomock-motor`) through the `get_database` dependency override. The real
Atlas database in `.env` is never read or written by the tests. SMTP is replaced
by an in-process capture, so no mail server is contacted either.

If MongoDB is unreachable the API still starts and serves `/api/health`;
database-backed routes return `500 database_error` with a generic body.

## Security rules

- `.env` and `.venv/` are git-ignored; only `.env.example` is tracked.
- Secrets are typed as `pydantic.SecretStr`, so they cannot leak via `repr()`
  or logs. Never log the connection string or object-storage keys.
- Passwords, hashes, raw reset tokens and access tokens are never logged and
  never returned in a response body.
- AWS credentials and the JWT secret stay **backend only**. Vite exposes just
  `VITE_*` variables to the browser, so never rename a secret to `VITE_*`.
- CORS must list explicit origins; `*` is rejected at start-up.
- `JWT_SECRET` must be at least 32 characters. A short or empty value is
  tolerated at import time so the health check still works, but the auth routes
  refuse to issue tokens and start-up logs an error.

### Local development and cookies

The shipped `.env` is production-oriented: `COOKIE_SECURE=true` with
`SameSite=none`, which is correct behind HTTPS but means a browser served over
plain `http://` will **silently discard the session cookie** and every
authenticated request will `401` for no obvious reason. The backend detects this
mismatch at start-up and says so in a log warning.

For local work, copy `backend/.env.development.example` to `backend/.env` to set
`COOKIE_SECURE=false` and `COOKIE_SAMESITE=lax`.

## Configuration

See `.env.example` for every supported variable name, and
`backend/.env.development.example` for local-development overrides.
