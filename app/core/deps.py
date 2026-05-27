from fastapi import Header

from app.core.exceptions import APIError


async def current_user_email(x_user_email: str | None = Header(default=None)) -> str:
    """Email из forward_auth (header X-User-Email). Без него запрос отклоняется —
    Caddy должен был не пропустить, но второй слой защиты на случай прямого хита."""
    if not x_user_email:
        raise APIError(401, "unauthorized", "Missing X-User-Email")
    return x_user_email


async def current_curator(
    x_user_email: str | None = Header(default=None),
    x_user_is_curator: str | None = Header(default=None),
) -> str:
    """Куратор-only endpoint. Полагается на forward_auth (auth-сервис ставит
    X-User-Is-Curator = '1' для кураторов)."""
    if not x_user_email:
        raise APIError(401, "unauthorized", "Missing X-User-Email")
    if (x_user_is_curator or "").strip() not in ("1", "true", "True"):
        raise APIError(403, "forbidden", "curator required")
    return x_user_email
