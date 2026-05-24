
import msgpack
import secrets
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.models.user import User
from app.schemas.auth import (
    RegisterRequest, LoginRequest,
    TokenResponse, UserResponse, ValidateResponse
)

from app.services.auth import hash_password, verify_password, create_access_token, decode_token

security = HTTPBearer()
router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=UserResponse)
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter_by(email=request.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists")

    user = User(
        email = request.email,
        password = hash_password(request.password),
        name = request.name
    )

    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user  = db.query(User).filter_by(email=request.email).first()

    if not user or not verify_password(request.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = create_access_token({"sub": str(user.id), "email": user.email, "role": user.role})

    return TokenResponse(access_token=access_token)



@router.get("/me", response_model=UserResponse)
def me(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)):

    if not credentials:
        raise HTTPException(status_code=401, detail="Токен не передан")
 
    token = credentials.credentials
    payload = decode_token(token)
 
    if not payload:
        raise HTTPException(status_code=401, detail="Токен недействителен")
 
    user = db.query(User).filter(User.id == payload["sub"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
 
    return user


@router.get("/validate", response_model=ValidateResponse)
def validate(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)):

    if not credentials:
        return ValidateResponse(valid=False)
 
    token = credentials.credentials
    payload = decode_token(token)
 
    if not payload:
        return ValidateResponse(valid=False)
    
    user = db.query(User).filter(User.id == payload["sub"]).first()
    if not user:
        return ValidateResponse(valid=False)
 
    return ValidateResponse(
        valid=True,
        user_id=str(user.id),
        email=user.email,
    )
@router.post("/validate/msgpack")
async def validate_msgpack(request: Request, db: Session = Depends(get_db)):
    body  = await request.body()
    data = msgpack.unpackb(body, raw=False)

    token = data.get('token')
    if not token:
        result = {"valid": False, "user_id": None, "email": None}
        return Response(
            content=msgpack.packb(result),
            media_type="application/msgpack"
        )
    
    payload = decode_token(token)
    if not payload:
        result = {"valid": False, "user_id": None, "email": None}
        return Response(
            content=msgpack.packb(result),
            media_type="application/msgpack"
        )
    
    user = db.query(User).filter(User.id == payload["sub"]).first()
    if not user:
        result = {"valid": False, "user_id": None, "email": None}
        return Response(
            content=msgpack.packb(result),
            media_type="application/msgpack"
        )
    
    result = {
        "valid": True,
        "user_id": str(user.id),
        "email": user.email,
    }

    return Response(
        content=msgpack.packb(result),
        media_type="application/msgpack"
    )

from app.models.telegram import TelegramAuthSession
import hmac
import hashlib

@router.post("/telegram/init")
def telegram_init(
    db: Session = Depends(get_db)
):
    state = secrets.token_urlsafe(32)
    session = TelegramAuthSession(state = state)
    db.add(session)
    db.commit()

    return {
        "state": state,
        "bot_url": f"https://t.me/{settings.TELEGRAM_BOT_USERNAME}?start={state}"
    }


@router.post("/telegram/webhook")
def telegram_webhook(
    request: dict,
    db: Session = Depends(get_db)
):
    state = request.get('state')
    tg_id = request.get('tg_id')
    username  = request.get("username", "")
    full_name = request.get("full_name", "")
    secret = request.get("secret")

    #секретная подпись получаемого сообщения. Убеждаемся, что получаем сообщение от нашего бота
    expected = hmac.new(
        settings.TELEGRAM_BOT_TOKEN.encode(), # ключ
        f"{tg_id}:{state}".encode(), # данные
        hashlib.sha256 # алгоритм
    ).hexdigest()

    if secret != expected:
        raise HTTPException(status_code=403, detail="Invalid secret")

    session = db.query(TelegramAuthSession).filter_by(state=state).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    email = f"{tg_id}"
    user = db.query(User).filter_by(email=email).first()
    if not user:
        user = User(email = email, name = full_name, role = 'user', password = hash_password(secrets.token_urlsafe(32)))
        db.add(user)
        db.commit()
        db.refresh(user)
    
    token = create_access_token({
        "sub": str(user.id),
        "email": user.email,
        "role": user.role
    })

    session.jwt_token = token
    db.commit()

    return {"ok": True}

@router.get("/telegram/token")
def telegram_token(state: str, db: Session = Depends(get_db)):
    session = db.query(TelegramAuthSession).filter_by(state=state).first()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if not session.jwt_token:
        return {"ready": False}

    token = session.jwt_token
    db.delete(session)
    db.commit()
    return {"ready": True, "access_token": token}


    


