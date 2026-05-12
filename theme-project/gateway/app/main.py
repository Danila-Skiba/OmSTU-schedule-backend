from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import Response
import msgpack
import httpx
from app.config import (
    AUTH_SERVICE_URL,
    NEWS_SERVICE_URL,
    SCHEDULE_SERVICE_URL,
    LECTURE_SERVICE_URL,
    PROTECTED_PREFIXES,
)

app = FastAPI(
    title="Gateway",
    description="API Gateway ОмГТУ",
    version="1.0.0",
)

# Маршруты
ROUTES = {
    "/api/auth":     AUTH_SERVICE_URL,
    "/api/news":     NEWS_SERVICE_URL,
    "/api/schedule": SCHEDULE_SERVICE_URL,
    "/api/lectures": LECTURE_SERVICE_URL,
}


async def validate_token(token: str) -> bool:
    """Проверяет токен через auth-service."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{AUTH_SERVICE_URL}/auth/validate",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5,
            )
            data = response.json()
            return data.get("valid", False)
    except Exception:
        return False

async def validate_token_msgpack(token: str) -> bool:
    try:
        async with httpx.AsyncClient() as client:
            body = msgpack.packb({"token": token})

            response  = await client.post(
                f"{AUTH_SERVICE_URL}/auth/validate/msgpack",
                content=body,
                headers={"Content-Type": "application/msgpack"},
                timeout=5,
            )
            data = msgpack.unpackb(response.content, raw=False)
            return data.get("valid")
    except Exception:
        return False
async def proxy(request: Request, target_url: str) -> Response:
    async with httpx.AsyncClient() as client:
        body = await request.body()

        response = await client.request(
            method=request.method,
            url=target_url,
            headers={k: v for k, v in request.headers.items() if k.lower() != "host"},
            content=body,
            params=request.query_params,
            timeout=30,
        )

        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.headers.get("content-type"),
        )


@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def gateway(request: Request, path: str):
    full_path = f"/api/{path}"

    target_base = None
    service_prefix = None
    for prefix, url in ROUTES.items():
        if full_path.startswith(prefix):
            target_base = url
            service_prefix = prefix
            break

    if not target_base:
        raise HTTPException(status_code=404, detail="Маршрут не найден")
    
    if any(full_path.startswith(p) for p in PROTECTED_PREFIXES):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Токен не передан")

        token = auth_header.split(" ")[1]
        valid = await validate_token_msgpack(token)
        if not valid:
            raise HTTPException(status_code=401, detail="Токен недействителен")

    # Убираем /api prefix и проксируем
    # /api/news/images/123 → /news/images/123
    service_path = full_path.replace("/api", "", 1)
    target_url = f"{target_base}{service_path}"

    return await proxy(request, target_url)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "gateway"}