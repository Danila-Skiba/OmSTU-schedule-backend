from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import Response
import msgpack
import httpx
from app.grpc_client import validate_token_grpc
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
    "/api/auth":     (AUTH_SERVICE_URL,     "/auth"),
    "/api/news":     (NEWS_SERVICE_URL,     ""),    
    "/api/schedule": (SCHEDULE_SERVICE_URL, "/schedule"),
    "/api/lectures": (LECTURE_SERVICE_URL,  "/lectures"),
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

async def validate_token_msgpack(token: str) -> dict:
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
            return data
    except Exception:
        return {'valid': False}
async def proxy(request: Request, target_url: str, user_id: str ) -> Response:
    async with httpx.AsyncClient() as client:
        body = await request.body()

        headers = {i: v for i, v in request.headers.items() if i.lower() != 'host'}
        if user_id: 
            headers['X-User-Id'] = user_id

        response = await client.request(
            method=request.method,
            url=target_url,
            headers=headers, 
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
    user_id = None 
    for prefix, (url, service_prefix) in ROUTES.items():
        if full_path.startswith(prefix):
            target_base = url
            service_path = service_prefix + full_path[len(prefix):]
            break

    if not target_base:
        raise HTTPException(status_code=404, detail="Маршрут не найден")
    
    if any(full_path.startswith(p) for p in PROTECTED_PREFIXES):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Токен не передан")

        token = auth_header.split(" ")[1]
        user_data  = validate_token_grpc(token)
        # print(f"user_data: {user_data}")
        if not user_data.get('valid'):
            raise HTTPException(status_code=401, detail="Токен недействителен")
        
        user_id = user_data.get('user_id')

    # Убираем /api prefix и проксируем
    # /api/news/images/123 → /news/images/123
    target_url = f"{target_base}{service_path}"

    return await proxy(request, target_url, user_id)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "gateway"}