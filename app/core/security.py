import secrets

from fastapi import HTTPException, Request, status
from pwdlib import PasswordHash

from app.core.config import settings

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_admin_credentials(username: str, password: str) -> bool:
    if not settings.admin_password_hash:
        return False
    username_ok = secrets.compare_digest(username, settings.admin_username)
    password_ok = password_hash.verify(password, settings.admin_password_hash)
    return username_ok and password_ok


def is_admin(request: Request) -> bool:
    return request.session.get("admin") == settings.admin_username


def require_admin(request: Request) -> None:
    if not is_admin(request):
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/admin/login"},
        )


def login_admin(request: Request) -> None:
    request.session.clear()
    request.session["admin"] = settings.admin_username
    ensure_csrf_token(request)


def logout_admin(request: Request) -> None:
    request.session.clear()


def ensure_csrf_token(request: Request) -> str:
    token = request.session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        request.session["csrf_token"] = token
    return token


def validate_csrf(request: Request, received_token: str) -> None:
    expected_token = request.session.get("csrf_token", "")
    if not expected_token or not secrets.compare_digest(expected_token, received_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token CSRF inválido.",
        )
