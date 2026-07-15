"""Журнал обращений к API: кто, куда, с каким результатом и как долго.

Даёт редакции простую аналитику использования (какими разделами реально пользуются) и
помогает разбирать инциденты — по журналу видно, чей запрос упал и сколько он занял.
Пишем в stdout: его собирает docker (`docker compose logs api`), отдельный файл внутри
контейнера не нужен и терялся бы при пересоздании.
"""
import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware

from auth.jwt_handler import decode_access_token

logger = logging.getLogger("api.access")

# Healthcheck ходит каждые 30 секунд — в журнале обращений это только шум.
_SKIP_PATHS = {"/health"}


def _editor(request) -> str:
    """Кто пришёл: id редактора из JWT. Сам токен в журнал не попадает."""
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        return "аноним"
    payload = decode_access_token(header[len("bearer "):])
    if payload and "user_id" in payload:
        return f"редактор#{payload['user_id']}"
    return "недействительный токен"


class RequestLogMiddleware(BaseHTTPMiddleware):
    """Пишет строку журнала на каждое обращение к API."""

    async def dispatch(self, request, call_next):
        if request.url.path in _SKIP_PATHS:
            return await call_next(request)

        started = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - started) * 1000

        # Путь без query-строки: параметры в журнал не тянем, чтобы туда не утекло лишнее.
        logger.info(
            "%s %s -> %s | %.0f мс | %s | %s",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
            _editor(request),
            request.client.host if request.client else "-",
        )
        return response
