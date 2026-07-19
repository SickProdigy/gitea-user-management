import os
from typing import Any

import httpx
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from starlette.middleware.sessions import SessionMiddleware

GITEA_BASE_URL = os.getenv("GITEA_BASE_URL", "http://gitea:3000").rstrip("/")
GITEA_TOKEN = os.getenv("GITEA_TOKEN", "")
PANEL_AUTH_TOKEN = os.getenv("PANEL_AUTH_TOKEN", "")
PANEL_SECRET_KEY = os.getenv("PANEL_SECRET_KEY", "change-me-before-use")
ALLOW_INSECURE_NO_AUTH = os.getenv("ALLOW_INSECURE_NO_AUTH", "false").lower() == "true"

app = FastAPI(title="Gitea User Management")
app.add_middleware(SessionMiddleware, secret_key=PANEL_SECRET_KEY, same_site="lax", https_only=False)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


class BulkActions(BaseModel):
    restricted: bool = False
    clear_website: bool = False
    clear_location: bool = False
    keep_email_private: bool = False
    disable_org_creation: bool = False
    prohibit_login: bool = False
    zero_repo_limit: bool = False
    visibility: str | None = Field(default=None, pattern="^(public|limited|private)$")


class BulkRequest(BaseModel):
    usernames: list[str]
    actions: BulkActions
    dry_run: bool = False


def auth_enabled() -> bool:
    return bool(PANEL_AUTH_TOKEN) or not ALLOW_INSECURE_NO_AUTH


def require_panel_auth(request: Request) -> None:
    if not auth_enabled():
        return
    if request.session.get("authenticated") is True:
        return
    raise HTTPException(status_code=401, detail="Panel login required")


def gitea_headers() -> dict[str, str]:
    if not GITEA_TOKEN:
        raise HTTPException(status_code=500, detail="GITEA_TOKEN is not configured")
    return {
        "Authorization": f"token {GITEA_TOKEN}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


async def gitea_request(method: str, path: str, **kwargs: Any) -> Any:
    url = f"{GITEA_BASE_URL}{path}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.request(method, url, headers=gitea_headers(), **kwargs)
    if response.status_code >= 400:
        detail = response.text
        try:
            detail = response.json()
        except ValueError:
            pass
        raise HTTPException(status_code=response.status_code, detail=detail)
    if not response.content:
        return None
    return response.json()


def normalize_user(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": user.get("id"),
        "login": user.get("login") or user.get("username"),
        "email": user.get("email", ""),
        "full_name": user.get("full_name", ""),
        "website": user.get("website", ""),
        "location": user.get("location", ""),
        "visibility": user.get("visibility", ""),
        "restricted": bool(user.get("restricted", False)),
        "prohibit_login": bool(user.get("prohibit_login", False)),
        "active": user.get("active"),
        "is_admin": bool(user.get("is_admin", user.get("admin", False))),
        "created": user.get("created") or user.get("created_at"),
        "last_login": user.get("last_login"),
        "allow_create_organization": user.get("allow_create_organization"),
        "max_repo_creation": user.get("max_repo_creation"),
        "login_name": user.get("login_name", ""),
        "source_id": user.get("source_id", 0),
    }


async def list_admin_users(page: int = 1, limit: int = 50) -> list[dict[str, Any]]:
    data = await gitea_request("GET", f"/api/v1/admin/users?page={page}&limit={limit}")
    return [normalize_user(user) for user in data]


async def find_admin_user(username: str) -> dict[str, Any]:
    # Gitea has no dedicated admin-get-user endpoint in older versions, so scan pages.
    page = 1
    while page <= 200:
        users = await list_admin_users(page=page, limit=50)
        if not users:
            break
        for user in users:
            if user.get("login") == username:
                return user
        page += 1
    raise HTTPException(status_code=404, detail=f"User not found: {username}")


def build_edit_payload(user: dict[str, Any], actions: BulkActions) -> dict[str, Any]:
    payload: dict[str, Any] = {
        # Gitea's edit-user API requires these even when they are not changing.
        "login_name": user.get("login_name") or "",
        "source_id": int(user.get("source_id") or 0),
    }
    if user.get("email"):
        payload["email"] = user["email"]
    if actions.restricted:
        payload["restricted"] = True
    if actions.clear_website:
        payload["website"] = ""
    if actions.clear_location:
        payload["location"] = ""
    if actions.disable_org_creation:
        payload["allow_create_organization"] = False
    if actions.prohibit_login:
        payload["prohibit_login"] = True
    if actions.zero_repo_limit:
        payload["max_repo_creation"] = 0
    if actions.visibility:
        payload["visibility"] = actions.visibility
    # Gitea's admin edit-user API does not expose the exact Keep Email Private
    # checkbox in all versions. For existing users, private visibility is the
    # supported API-level privacy control this panel can apply safely.
    if actions.keep_email_private and "visibility" not in payload:
        payload["visibility"] = "private"
    return payload


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    if auth_enabled() and not request.session.get("authenticated"):
        return templates.TemplateResponse("login.html", {"request": request})
    return templates.TemplateResponse("index.html", {"request": request, "gitea_base_url": GITEA_BASE_URL})


@app.post("/login")
async def login(request: Request, token: str = Form(...)) -> RedirectResponse:
    if not PANEL_AUTH_TOKEN:
        raise HTTPException(status_code=500, detail="PANEL_AUTH_TOKEN is not configured")
    if token != PANEL_AUTH_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid panel token")
    request.session["authenticated"] = True
    return RedirectResponse("/", status_code=303)


@app.post("/logout")
async def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return RedirectResponse("/", status_code=303)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/users")
async def api_users(request: Request, page: int = 1, limit: int = 50) -> dict[str, Any]:
    require_panel_auth(request)
    limit = min(max(limit, 1), 100)
    users = await list_admin_users(page=page, limit=limit)
    return {"page": page, "limit": limit, "users": users}


@app.post("/api/users/bulk")
async def api_bulk_users(request: Request, bulk: BulkRequest) -> JSONResponse:
    require_panel_auth(request)
    usernames = sorted(set(name.strip() for name in bulk.usernames if name.strip()))
    if not usernames:
        raise HTTPException(status_code=400, detail="No users selected")

    results: list[dict[str, Any]] = []
    for username in usernames:
        try:
            user = await find_admin_user(username)
            payload = build_edit_payload(user, bulk.actions)
            if bulk.dry_run:
                results.append({"username": username, "status": "dry-run", "payload": payload})
            else:
                updated = await gitea_request("PATCH", f"/api/v1/admin/users/{username}", json=payload)
                results.append({"username": username, "status": "updated", "user": normalize_user(updated)})
        except HTTPException as exc:
            results.append({"username": username, "status": "error", "detail": exc.detail})

    status_code = 207 if any(result["status"] == "error" for result in results) else 200
    return JSONResponse({"results": results}, status_code=status_code)
