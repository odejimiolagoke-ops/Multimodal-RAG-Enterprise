import base64
import os
import tempfile
from functools import partial
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, model_validator

from access import authorize
from auth import DEFAULT_USERS, create_token, get_user, register_auth_middleware, register_user
from guardrails import (
    MAX_AUDIO_BYTES,
    MAX_IMAGE_BYTES,
    MAX_PDF_BYTES,
    read_guarded_upload,
    validate_image_bytes,
    validate_text_input,
)
from log import register_logging_middleware
from pipeline import query_documents, rag_query
from rag import index_file

app = FastAPI(title="Enterprise Multimodal RAG API")
register_auth_middleware(app)
register_logging_middleware(app)


class TextQuery(BaseModel):
    text: str | None = None
    question: str | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_question(cls, values):
        if isinstance(values, dict):
            if values.get("text") is None and values.get("question") is not None:
                values["text"] = values["question"]
        return values

    @model_validator(mode="after")
    def validate_question(self):
        self.text = validate_text_input(self.text or self.question or "", "question")
        return self


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str


class SpeechRequest(BaseModel):
    text: str

    @model_validator(mode="after")
    def validate_text(self):
        self.text = validate_text_input(self.text, "text")
        return self


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/public/register")
async def register(payload: RegisterRequest):
    username = payload.username.strip()
    password = payload.password
    if not username:
        raise HTTPException(status_code=400, detail="username is required")
    if len(password) < 4:
        raise HTTPException(status_code=400, detail="password must be at least 4 characters")
    try:
        user = register_user(username, password)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"status": "registered", "username": username.lower(), "role": user["role"]}


@app.post("/public/login")
async def login(payload: LoginRequest):
    username = payload.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="username is required")

    user = get_user(username)
    if not user or user["password"] != payload.password:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_token(username.lower(), user["role"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "username": username.lower(),
        "role": user["role"],
    }


@app.get("/profile")
async def profile(request: Request):
    return {
        "user": getattr(request.state, "user", "anonymous"),
        "role": getattr(request.state, "role", "guest"),
    }


@app.get("/admin/stats")
async def admin_stats(request: Request, _: bool = authorize("admin")):
    return {
        "user": getattr(request.state, "user", "anonymous"),
        "role": getattr(request.state, "role", "guest"),
        "message": "Admin access granted",
    }


@app.post("/text-query")
async def text_query(payload: TextQuery):
    query = validate_text_input(payload.text or payload.question or "", "question")
    return {
        "query": query,
        "results": query_documents(query),
        "answer": rag_query(query),
    }


@app.post("/text-to-speech")
async def text_to_speech(payload: SpeechRequest):
    text = validate_text_input(payload.text, "text")
    try:
        from vlm import text_to_speech as synthesize_speech

        return {"audio_base64": synthesize_speech(text)}
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Text-to-speech is unavailable") from exc


@app.post("/pdf-upload")
async def pdf_upload(file: UploadFile = File(...), _: bool = authorize("admin")):
    if not file.filename or Path(file.filename).suffix.lower() != ".pdf":
        raise HTTPException(status_code=400, detail="A PDF file is required")
    content = await read_guarded_upload(file, MAX_PDF_BYTES, "PDF")
    try:
        result = index_file(content, file.filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Document storage is unavailable. Check the Supabase URL and service-role key in .env.",
        ) from exc
    return {"status": "PDF uploaded and indexed", **result}


@app.post("/voice-query")
async def voice_query(file: UploadFile = File(...)):
    suffix = Path(file.filename or "audio.wav").suffix or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_file.write(await read_guarded_upload(file, MAX_AUDIO_BYTES, "Audio file"))
        temp_path = temp_file.name
    try:
        from vlm import transcribe_audio

        transcription = validate_text_input(
            await run_in_threadpool(transcribe_audio, temp_path),
            "transcription",
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Speech-to-text failed: {exc}") from exc
    finally:
        try:
            Path(temp_path).unlink(missing_ok=True)
        except Exception:
            pass
    return {
        "transcription": transcription,
        "results": query_documents(transcription),
        "answer": await run_in_threadpool(rag_query, transcription),
    }


@app.post("/image-query")
async def image_query(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Image file is required")
    image_bytes = await read_guarded_upload(file, MAX_IMAGE_BYTES, "Image")
    validate_image_bytes(image_bytes)
    caption = "Uploaded image."
    return {"caption": caption, "results": query_documents(caption), "answer": rag_query(caption)}


@app.post("/vlm-speech")
async def vlm_speech(
    question: str = Form(default=""),
    audio: UploadFile | None = File(default=None),
    image: UploadFile | None = File(default=None),
    return_audio: bool = Form(default=True),
):
    try:
        from vlm import generate_vlm_answer, text_to_speech, transcribe_audio
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"VLM speech pipeline is unavailable: {exc}") from exc

    audio_path = None
    if question.strip():
        question = validate_text_input(question, "question")

    if audio is not None:
        suffix = Path(audio.filename or "audio.wav").suffix or ".wav"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_audio:
            temp_audio.write(await read_guarded_upload(audio, MAX_AUDIO_BYTES, "Audio file"))
            audio_path = temp_audio.name
        try:
            question = validate_text_input(
                await run_in_threadpool(transcribe_audio, audio_path),
                "transcription",
            )
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"Speech-to-text failed: {exc}") from exc
        finally:
            Path(audio_path).unlink(missing_ok=True)

    if image is not None:
        if not question.strip():
            question = "Describe the uploaded image."
        suffix = Path(image.filename or "image.png").suffix or ".png"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_image:
            image_bytes = await read_guarded_upload(image, MAX_IMAGE_BYTES, "Image")
            validate_image_bytes(image_bytes)
            temp_image.write(image_bytes)
            image_path = temp_image.name
        try:
            if not question.strip():
                raise HTTPException(status_code=400, detail="A question or transcript is required for image analysis")
            knowledge_context = "\n".join(
                item.get("content", "")
                for item in query_documents(question)
                if item.get("content")
            )
            answer = await run_in_threadpool(
                generate_vlm_answer,
                image_path,
                question,
                knowledge_context,
            )
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"Vision model failed: {exc}") from exc
        finally:
            Path(image_path).unlink(missing_ok=True)
    else:
        if not question.strip():
            raise HTTPException(status_code=400, detail="No question was provided or transcribed")
        answer = await run_in_threadpool(rag_query, question)

    response = {"transcript": question, "reasoning": answer}
    if return_audio:
        try:
            response["audio_base64"] = await run_in_threadpool(text_to_speech, answer)
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"Text-to-speech failed: {exc}") from exc
    return response
