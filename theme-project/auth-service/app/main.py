from fastapi import FastAPI
from fastapi.security import HTTPBearer
from app.routers import auth
import threading
from app.grpc_server import serve
from app.bot import run_bot

grpc_thread = threading.Thread(target=serve, daemon=True)
grpc_thread.start()

bot_thread = threading.Thread(target=run_bot , daemon=True)
bot_thread.start()

app = FastAPI(
    title='Auth Service',
    description='Сервис Авторизации',
)

security = HTTPBearer()
app.include_router(auth.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "auth-service"}

