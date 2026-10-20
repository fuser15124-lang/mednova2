from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
import io
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import select
from pypdf import PdfReader
from app.config import settings
from app.db import Base, engine, get_db
from app.models import User, Conversation, Message, Document
from app.security import hash_password, verify_password, create_token, current_user
from app.ai import answer
from app.pubmed import search_pubmed

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(title=settings.app_name, version="0.1.0", description="Multilingual medical information starter; not a diagnostic device.", lifespan=lifespan)
cors_origins = [origin.strip().rstrip("/") for origin in settings.cors_origins.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
STATIC = Path(__file__).resolve().parent.parent / "static"

class RegisterIn(BaseModel):
    email: str = Field(min_length=5, max_length=320)
    password: str = Field(min_length=10, max_length=128)
    language: str = "en"
    role: str = "general"
class LoginIn(BaseModel):
    email: str
    password: str
class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=12000)
    conversation_id: int | None = None
    language: str = "en"
class LanguageIn(BaseModel): language: str

@app.get("/api/health")
def health():
    return {"status": "ok", "service": settings.app_name, "ai_configured": bool(settings.ai_api_key and settings.ai_model), "evidence_provider": "PubMed E-utilities", "clinical_validation": False}

@app.post("/api/auth/register")
def register(data: RegisterIn, db: Session = Depends(get_db)):
    email = data.email.strip().lower()
    if "@" not in email or "." not in email.rsplit("@",1)[-1]: raise HTTPException(422, "Enter a valid email address")
    if data.language not in {"fa","en","es","it","ru","he"}: raise HTTPException(422, "Unsupported language")
    if data.role not in {"general", "student", "professional"}: raise HTTPException(422, "Unsupported role")
    if data.role == "professional": raise HTTPException(403, "Professional access requires a verification workflow, which is not enabled in this starter")
    if db.scalar(select(User).where(User.email == email)): raise HTTPException(409, "An account with this email already exists")
    user = User(email=email, password_hash=hash_password(data.password), language=data.language, role=data.role)
    db.add(user); db.commit(); db.refresh(user)
    return {"access_token": create_token(user), "token_type": "bearer", "user": {"id": user.id, "email": user.email, "language": user.language, "role": user.role}}

@app.post("/api/auth/login")
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == data.email.strip().lower()))
    if not user or not verify_password(data.password, user.password_hash): raise HTTPException(401, "Incorrect email or password")
    return {"access_token": create_token(user), "token_type": "bearer", "user": {"id": user.id, "email": user.email, "language": user.language, "role": user.role}}

@app.get("/api/auth/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "email": user.email, "language": user.language, "role": user.role}

@app.post("/api/auth/language")
def set_language(data: LanguageIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if data.language not in {"fa","en","es","it","ru","he"}: raise HTTPException(422, "Unsupported language")
    user.language = data.language; db.commit(); return {"language": user.language}

@app.post("/api/chat")
async def chat(data: ChatIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    lang = data.language if data.language in {"fa","en","es","it","ru","he"} else user.language
    conv = db.get(Conversation, data.conversation_id) if data.conversation_id else None
    if conv and conv.user_id != user.id: raise HTTPException(404, "Conversation not found")
    if not conv:
        conv = Conversation(user_id=user.id, title=data.message[:70], language=lang)
        db.add(conv); db.commit(); db.refresh(conv)
    db.add(Message(conversation_id=conv.id, role="user", content=data.message)); db.commit()
    history = db.scalars(select(Message).where(Message.conversation_id == conv.id).order_by(Message.id.desc()).limit(20)).all()
    history = list(reversed(history))
    try:
        response = await answer([{"role": m.role, "content": m.content} for m in history], lang)
    except HTTPException:
        raise
    db.add(Message(conversation_id=conv.id, role="assistant", content=response))
    conv.updated_at = datetime.now(timezone.utc); db.commit()
    return {"conversation_id": conv.id, "answer": response, "language": lang, "disclaimer": "AI-generated information can be inaccurate; this is not a diagnosis or a substitute for professional care."}

@app.get("/api/conversations")
def conversations(db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.scalars(select(Conversation).where(Conversation.user_id == user.id).order_by(Conversation.updated_at.desc())).all()
    return [{"id": c.id, "title": c.title, "language": c.language, "updated_at": c.updated_at.isoformat()} for c in rows]

@app.get("/api/conversations/{conversation_id}")
def conversation_detail(conversation_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    c = db.get(Conversation, conversation_id)
    if not c or c.user_id != user.id: raise HTTPException(404, "Conversation not found")
    return {"id": c.id, "title": c.title, "language": c.language, "messages": [{"id":m.id,"role":m.role,"content":m.content,"created_at":m.created_at.isoformat()} for m in c.messages]}

@app.delete("/api/conversations/{conversation_id}")
def delete_conversation(conversation_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    c = db.get(Conversation, conversation_id)
    if not c or c.user_id != user.id: raise HTTPException(404, "Conversation not found")
    db.delete(c); db.commit(); return {"deleted": True}

@app.get("/api/evidence/pubmed")
async def evidence(q: str = Query(min_length=1, max_length=300), page: int = 1, page_size: int = 10, user: User = Depends(current_user)):
    return await search_pubmed(q, page, page_size)

@app.post("/api/documents")
async def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(current_user)):
    allowed = {"application/pdf", "text/plain"}
    if file.content_type not in allowed: raise HTTPException(415, "Only PDF and plain-text files are supported in this starter")
    raw = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(raw) > settings.max_upload_mb * 1024 * 1024: raise HTTPException(413, f"File exceeds {settings.max_upload_mb} MB limit")
    name = Path(file.filename or "document").name[:255]
    if file.content_type == "application/pdf":
        if not raw.startswith(b"%PDF-"): raise HTTPException(415, "File signature does not match PDF")
        try: text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(raw)).pages)
        except Exception: raise HTTPException(422, "PDF could not be read")
    else:
        try: text = raw.decode("utf-8-sig")
        except UnicodeDecodeError: raise HTTPException(422, "Text file must be UTF-8 encoded")
    doc = Document(user_id=user.id, filename=name, content_type=file.content_type, extracted_text=text[:500000])
    db.add(doc); db.commit(); db.refresh(doc)
    return {"id": doc.id, "filename": doc.filename, "content_type": doc.content_type, "characters_extracted": len(doc.extracted_text), "preview": doc.extracted_text[:1200], "note": "Extraction is not OCR and has not been clinically validated."}

@app.get("/api/documents")
def documents(db: Session = Depends(get_db), user: User = Depends(current_user)):
    docs = db.scalars(select(Document).where(Document.user_id == user.id).order_by(Document.id.desc())).all()
    return [{"id":d.id,"filename":d.filename,"content_type":d.content_type,"characters_extracted":len(d.extracted_text),"created_at":d.created_at.isoformat()} for d in docs]

@app.get("/", include_in_schema=False)
def index(): return FileResponse(STATIC / "index.html")
@app.get("/app.js", include_in_schema=False)
def js(): return FileResponse(STATIC / "app.js", media_type="text/javascript")
@app.get("/styles.css", include_in_schema=False)
def css(): return FileResponse(STATIC / "styles.css", media_type="text/css")
