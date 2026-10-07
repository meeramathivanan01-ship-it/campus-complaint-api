# Campus Complaint & Maintenance Management API

A REST API for recording campus facilities issues, managing their repair, and collecting student feedback after a complaint is resolved. Students submit and track their own complaints, administrators manage and assign work, and maintenance staff work on complaints assigned to them.

## Features

- Student registration and login with JWT bearer authentication.
- Role-based access for `student`, `admin`, and `maintenance` users.
- Complaint creation and CRUD operations, with student ownership checks.
- Complaint status transitions: `pending` → `in_progress` → `resolved` → `closed`.
- Admin assignment of complaints to maintenance users.
- Maintenance access to their assigned complaints and status updates limited to those assignments.
- One student rating (1–5) and optional comment per complaint, after it is resolved or closed.
- Admin statistics for complaint status, assignments, feedback count, and average rating.
- Consistent error responses for HTTP errors, request validation errors, and unexpected server errors.
- Automated unit tests using Python `unittest`.

## Technology

- Python
- FastAPI and Uvicorn
- Pydantic
- SQLAlchemy with SQLite
- JWT via `python-jose`
- Password hashing via Passlib and bcrypt
- Python `unittest`

## Project structure

```text
campus-complaint-api/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   ├── security.py
│   └── routers/
│       ├── auth.py
│       └── complaints.py
├── tests/
├── .gitignore
├── requirements.txt
└── README.md
```

The SQLite database file (`campus_complaints.db`) is created in the project root when the application initializes the database. It is ignored by Git along with `.env` and virtual environments. There is no `requirements-dev.txt` currently.

Application configuration is centralized in `app/config.py`; standard logging is configured in `app/logging_config.py`.

## Local setup

Clone the repository and enter its directory:

```bash
git clone <repository-url>
cd campus-complaint-api
```

Create and activate a virtual environment. On Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

On macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the project dependencies, including Uvicorn, which serves the FastAPI app:

```bash
python -m pip install -r requirements.txt
```

Create a `.env` file in the project root and set a private signing key. For example, use this placeholder and replace it with a securely generated value:

```env
SECRET_KEY=your-secret-key-here
# Optional; defaults to the project-root SQLite database.
DATABASE_PATH=campus_complaints.db
# Optional; defaults to development.
ENVIRONMENT=development
# Optional; defaults to INFO. Supported levels: DEBUG, INFO, WARNING, ERROR, CRITICAL.
LOG_LEVEL=INFO
```

`DATABASE_PATH` may be an absolute path or a path relative to the project root. `ENVIRONMENT` is currently configuration metadata; it does not enable different application behavior.
The application checks for `SECRET_KEY` during startup and stops with a clear configuration error if it is missing.

## Logging

The application uses Python's standard logging module with timestamp, severity, logger name, and message fields. Set `LOG_LEVEL` to `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`; it defaults to `INFO`. Startup, authentication and authorization outcomes, complaint workflow events, and unexpected exceptions are logged. Credentials, tokens, request bodies, and database URLs are not included in application event messages. Uvicorn handles HTTP access logs when serving the app.

Do not commit `.env`. For local development, start the API from the project root:

```bash
python -m uvicorn app.main:app --reload
```

For deployment, run without `--reload` and provide configuration through the deployment environment or a private `.env` file. Keep `SECRET_KEY` private and use a durable location for `DATABASE_PATH` so the SQLite database survives restarts. Put the service behind a TLS-terminating reverse proxy when it is reachable outside a trusted network.

Interactive API documentation is available at `http://127.0.0.1:8000/docs`. ReDoc is available at `http://127.0.0.1:8000/redoc`.

## Authentication

1. Register with `POST /auth/register`, providing a name, email, and password. Registration does not accept a role; newly registered users receive the model's default `student` role.
2. Log in with `POST /auth/login` to receive an access token.
3. For protected routes, send the token in the HTTP header `Authorization: Bearer <access-token>`.
4. The API validates the JWT and loads the current user from the database before applying role and ownership checks. Tokens expire after 30 minutes.

Never put real credentials, tokens, or signing keys in source control, examples, or issue reports.

## Roles and permissions

| Role | Capabilities |
| --- | --- |
| `student` | Create complaints; list, view, update, and delete only their own complaints; submit one rating and optional comment for their own resolved or closed complaint. Students cannot change operational status. |
| `admin` | Create and manage complaints across students; assign complaints to maintenance users; update complaint statuses; view complaint statistics. |
| `maintenance` | View complaints assigned to their own user ID and update the status of those assigned complaints. They cannot access all complaints or assign work. |

The complaints health endpoint is public. All other complaint endpoints in the table below require authentication and the listed role.

## Complaint lifecycle

The operational status workflow is:

```text
pending → in_progress → resolved → closed
```

Each status update must advance to the next status in this sequence. Admins can manage complaint status. Maintenance users can advance status only for complaints assigned to them. Assignment is a separate nullable relationship and does not add an `assigned` status or change the status by itself. Resolving a complaint records `resolved_at`.

Students can edit complaint details through the complaint update endpoint, but status is not an editable field there.

## API endpoints

`/` below denotes the trailing slash used by the registered collection routes.

| Method | Endpoint | Purpose | Access |
| --- | --- | --- | --- |
| `POST` | `/auth/register` | Register a student account | Public |
| `POST` | `/auth/login` | Authenticate and receive a JWT | Public |
| `GET` | `/` | API health/message | Public |
| `GET` | `/complaints/health` | Complaints router health check | Public |
| `POST` | `/complaints/` | Create a complaint | Student or admin |
| `GET` | `/complaints/` | Paginated complaint list; students see their own | Student or admin |
| `GET` | `/complaints/{complaint_id}` | Get a complaint; students can access their own | Student or admin |
| `PUT` | `/complaints/{complaint_id}` | Update complaint details; students can update their own | Student or admin |
| `DELETE` | `/complaints/{complaint_id}` | Delete a complaint; students can delete their own | Student or admin |
| `PUT` | `/complaints/{complaint_id}/assign` | Assign to a maintenance user by `maintenance_user_id` | Admin |
| `GET` | `/complaints/assigned` | List complaints assigned to the current maintenance user | Maintenance |
| `PUT` | `/complaints/{complaint_id}/status` | Advance complaint status; maintenance is limited to assigned complaints | Admin or assigned maintenance user |
| `POST` | `/complaints/{complaint_id}/feedback` | Submit a 1–5 rating and optional comment | Owning student; complaint must be resolved or closed |
| `GET` | `/complaints/stats` | View aggregate complaint and feedback statistics | Admin |

The complaint list accepts `skip` and `limit` query parameters. It defaults to `GET /complaints/?skip=0&limit=20`; `skip` must be nonnegative and `limit` must be between 1 and 100. Results are ordered by complaint ID ascending before pagination. Students receive pages only from their own complaints; admins receive pages from all complaints.

Complaint status updates accept a JSON body such as:

```json
{"status": "in_progress"}
```

Assignment accepts a JSON body such as:

```json
{"maintenance_user_id": 12}
```

Feedback accepts a JSON body such as:

```json
{"rating": 5, "comment": "Thank you for resolving this."}
```

## Error responses

HTTP errors use a JSON body with `error` and `status_code`. Validation errors also include field-level `detail` entries containing the location, message, and error type. Status codes remain meaningful, including `401` for missing or invalid authentication, `403` for disallowed roles, `404` for missing or inaccessible complaints, `409` for duplicate feedback or feedback submitted before resolution, and `422` for invalid request data. JWT authentication errors retain the `WWW-Authenticate: Bearer` header.

## Security notes

- JWT signing uses `SECRET_KEY` from the environment (loaded from the local `.env` file when present).
- `.env` is ignored by Git; keep it private and do not commit it.
- Passwords are hashed with Passlib's bcrypt context and are not returned by user response schemas.
- Role checks and student ownership checks are separate; both are applied where appropriate.
- Error responses do not return stack traces or internal exception text.

## Tests

Run the test suite from the repository root:

```bash
python -m unittest discover -s tests -v
```

The tests cover role authorization, complaint ownership, assignment validation and access, status transitions, feedback validation and eligibility, dashboard statistics, database initialization, error response formatting, configuration, and logging.

## Current limitations

- Assignment history is not stored; each assignment replaces the current maintenance user.
- There is no general database migration framework. Startup initialization creates missing tables and includes the current additive SQLite assignment-column upgrade.
- Feedback can be submitted, and aggregate feedback statistics are available, but there is no endpoint to retrieve individual feedback.
- Complaint list endpoints do not currently support filtering.

## Future improvements

- Add an assignment history/audit trail.
- Adopt a versioned database migration tool for schema changes.
- Add useful filters to complaint listings.
- Evaluate a production database and deployment configuration for the target environment.
- Add operational monitoring and deployment-specific health checks.
