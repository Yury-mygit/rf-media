from fastapi import Header

from app.core.exceptions import APIError


async def current_user_email(x_user_email: str | None = Header(default=None)) -> str:
    """Email из forward_auth (header X-User-Email). Без него запрос отклоняется —
    Caddy должен был не пропустить, но второй слой защиты на случай прямого хита."""
    if not x_user_email:
        raise APIError(401, "unauthorized", "Missing X-User-Email")
    return x_user_email


async def current_uploader(
    x_user_email: str | None = Header(default=None),
    x_uploader_system: str | None = Header(default=None),
    x_uploader_id: str | None = Header(default=None),
) -> str:
    """Identity для upload-эндпоинтов. Два источника:

    - **Server-to-server из сервисов со своей user-моделью** (booking и т.п.):
      `X-Uploader-System` + `X-Uploader-Id` → возвращаем композит
      `"<system>:<id>"`. Surrogate имеет приоритет (если присланы оба).
    - **Forward_auth из raftforge-auth** (board/notes/docs/прямой UI):
      `X-User-Email` → возвращаем email как есть (backward compat).

    Записывается в `Asset.uploaded_by` (String(255)). Migration в
    `uploaded_by_uuid` — Phase 3 identity-roadmap'а."""
    if x_uploader_system and x_uploader_id:
        if ":" in x_uploader_system:
            raise APIError(400, "bad_request", "X-Uploader-System must not contain ':'")
        return f"{x_uploader_system}:{x_uploader_id}"
    if x_user_email:
        return x_user_email
    raise APIError(
        401,
        "unauthorized",
        "Missing identity (X-Uploader-System+X-Uploader-Id or X-User-Email)",
    )


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
