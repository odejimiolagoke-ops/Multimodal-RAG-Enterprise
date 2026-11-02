import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.responses import JSONResponse
from jose import JWTError, jwt

security = HTTPBearer(auto_error=False)
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-this-secret-key")
ALGORITHM = "HS256"

USER_DB_PATH = Path(__file__).resolve().parent / "users.json"

DEFAULT_USERS = {
    "admin": {"password": "admin123", "role": "admin"},
}


def _load_registered_users():
    if not USER_DB_PATH.exists():
        USER_DB_PATH.write_text("{}", encoding="utf-8")
    try:
        with USER_DB_PATH.open("r", encoding="utf-8") as file:
            data = json.load(file)
        return {str(k).strip().lower(): v for k, v in (data or {}).items()}
    except (json.JSONDecodeError, TypeError):
        USER_DB_PATH.write_text("{}", encoding="utf-8")
        return {}


REGISTERED_USERS = _load_registered_users()


def _save_registered_users():
    with USER_DB_PATH.open("w", encoding="utf-8") as file:
        json.dump(REGISTERED_USERS, file, indent=2)


def register_user(username: str, password: str):
    normalized = username.strip().lower()
    if not normalized:
        raise ValueError("username is required")
    if len(password) < 4:
        raise ValueError("password must be at least 4 characters")
    if normalized in DEFAULT_USERS or normalized in REGISTERED_USERS:
        raise ValueError("username already exists")
    REGISTERED_USERS[normalized] = {"password": password, "role": "user"}
    _save_registered_users()
    return REGISTERED_USERS[normalized]


def get_user(username: str):
    normalized = username.strip().lower()
    return DEFAULT_USERS.get(normalized) or REGISTERED_USERS.get(normalized)


def create_token(username: str, role: str) -> str:
    payload = {
        "sub": username,
        "user": username,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=8),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc


def register_auth_middleware(app):
    @app.middleware("http")
    async def verify_request_token(request: Request, call_next):
        allowed_paths = {"/health", "/docs", "/openapi.json", "/redoc", "/public/login", "/public/register"}
        if request.url.path.startswith("/public") or request.url.path in allowed_paths:
            return await call_next(request)
        if request.method == "OPTIONS":
            return await call_next(request)

        auth: HTTPAuthorizationCredentials | None = await security(request)
        if not auth or not auth.credentials:
            return JSONResponse(status_code=401, content={"detail": "Authorization required"})

        try:
            payload = decode_token(auth.credentials)
        except HTTPException as exc:
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
        request.state.user = payload.get("user", "anonymous")
        request.state.role = payload.get("role", "guest")
        response = await call_next(request)
        return response

    return app
