from fastapi import APIRouter, Depends, HTTPException, Header, UploadFile, File
from app.database import get_db
from fastapi.responses import Response
# from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.models.lecture import Session, Fragment
from sqlalchemy.orm import Session as DBSession
from app.config import settings
from app.services.gigachat import send_photo, compile_fragments
import uuid
import msgpack
from datetime import datetime
# import httpx

# security = HTTPBearer()
router = APIRouter(prefix="/lectures", tags=["lectures"])

# def get_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
#     if not credentials:
#         raise HTTPException(status_code=401, detail="Токен не передан")

#     token = credentials.credentials
#     try:
#         response = httpx.get(
#             f"{settings.AUTH_SERVICE_URL}/auth/validate",
#             headers={"Authorization": f"Bearer {token}"},
#             timeout = 5
#         )
#         data = response.json()
#     except Exception as e:
#         raise HTTPException(status_code=403, detail="Auth сервис не доступен")
    
#     if not data.get("valid"):
#         raise HTTPException(status_code=403, detail="Токен недействителен")

#     return data["user_id"]

def get_user_id(x_user_id: str = Header(None, alias="X-User-Id")):
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Токен не передан")
    return x_user_id

    

# def get_user_id_msgpack(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
#     if not credentials:
#         raise HTTPException(status_code=401, detail="Токен не передан")

#     token = credentials.credentials
#     try:
#         body = msgpack.packb({"token": token})




@router.post("/session")
def create_session(
    subject: str,
    user_id: str = Depends(get_user_id),
    db: DBSession = Depends(get_db)
    ):
    session = Session(
        user_id=uuid.UUID(user_id),
        subject = subject
    )

    db.add(session)
    db.commit()
    db.refresh(session)

    return {
        "session_id": str(session.id),
        "subject": session.subject,
        "created_at": session.created_at
    }

@router.post("/session/{session_id}/data")
async def load_photo(
    session_id: str,
    comment: str,
    file: UploadFile = File(...),
    user_id: str = Depends(get_user_id),
    db: DBSession = Depends(get_db)
):
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if str(session.user_id) != user_id:
        raise HTTPException(status_code=403, detail="You are not owner of this session")
    
    image_bytes = await file.read()
    if len(image_bytes) > 15* 1024**2:
        raise HTTPException(status_code=400, detail="Image size must be less than 15MB")

    try:
        import asyncio
        md_text, gigachat_image_id = await asyncio.to_thread(
            send_photo, image_bytes, file.filename or "image.jpg", comment
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send photo to Gigacha {e}")

    last_fragment = db.query(Fragment).filter_by(session_id = session_id).order_by(Fragment.index.desc()).first()
    index = (last_fragment.index + 1) if last_fragment else 1

    fragment = Fragment(
        session_id = uuid.UUID(session_id),
        index = index,
        markdown_text = md_text,
        gigachat_file_id = gigachat_image_id,
    )

    db.add(fragment)

    db.commit()

    return {
        "fragment_index": index, 
        "md_text": md_text
    }

@router.post("/session/{session_id}/compile")
async def compile(
    session_id: str,
    user_id: str = Depends(get_user_id),
    db: DBSession = Depends(get_db)
):
    
    
    session = db.query(Session).filter_by(id=session_id).first()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if str(session.user_id) != user_id:
        raise HTTPException(status_code=403, detail="You are not owner of this session")
    
    fragments = db.query(Fragment).filter_by(session_id=session_id).order_by(Fragment.index).all()

    if not fragments:
        raise HTTPException(status_code=404, detail="No fragments found")
    md_content = compile_fragments([frag.markdown_text for frag in fragments], session.subject)

    session.md_content = md_content

    session.compiled_at = datetime.now() 

    db.query(Fragment).filter_by(session_id=session_id).delete()
    db.commit()

    return {
        "md_content": md_content,
        "session_id": str(session.id)
    }
    

@router.get("/lectures")
def get_lectures(
    user_id: str = Depends(get_user_id),
    db: DBSession = Depends(get_db)
):
    sessions = db.query(Session).filter_by(user_id=uuid.UUID(user_id)).order_by(Session.created_at.desc()).all()

    return [
        {
            "session_id": str(s.id),
            "subject": s.subject,
            "created_at": s.created_at,
            "compiled_at": s.compiled_at,
            "is_compiled": s.compiled_at is not None,
        }
        for s in sessions
    ]

@router.get("/session/{session_id}")
def get_session(
    session_id: str,
    user_id: str = Depends(get_user_id),
    db: DBSession = Depends(get_db)
):
    

    session = db.query(Session).filter_by(id=session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if str(session.user_id) != user_id:
        raise HTTPException(status_code=403, detail="You are not owner of this session")

    return {
        "session_id": str(session.id),
        "subject": session.subject,
        "created_at": session.created_at,
        "compiled_at": session.compiled_at,
        "is_compiled": session.compiled_at is not None,
        'md_content': session.md_content 
    }
    
    

@router.delete("/session/{session_id}")
def delete_session(
    session_id: str,
    user_id: str = Depends(get_user_id),
    db: DBSession = Depends(get_db)
):

    session = db.query(Session).filter_by(id = session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if str(session.user_id) != user_id:
        raise HTTPException(status_code=403, detail="You are not owner of this session")
    
    db.query(Fragment).filter_by(session_id=session_id).delete()

    db.delete(session)
    db.commit()


    

