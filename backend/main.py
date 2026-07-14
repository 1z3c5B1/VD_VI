import asyncio
import base64
import uuid
import requests
import requests.utils
from pathlib import Path
from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Optional

from backend.models.image_generator import ImageGenerator
from backend.models.video_generator import VideoGenerator
from backend.config import OUTPUT_DIR, STATIC_DIR, BASE_DIR, POLLINATIONS_PK, HF_TOKEN
from backend.auth import register, login, verify_token

image_generator = ImageGenerator()
video_generator = VideoGenerator()

app = FastAPI(title="VD AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = BASE_DIR / "frontend"

STATIC_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static/generated", StaticFiles(directory=str(STATIC_DIR)), name="static_generated")
app.mount("/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")


class ImageRequest(BaseModel):
    prompt: str
    negative_prompt: Optional[str] = None
    width: int = 1024
    height: int = 1024
    guidance_scale: float = 7.5
    num_inference_steps: int = 25
    seed: Optional[int] = None


class ImageEditRequest(BaseModel):
    image_data: str
    prompt: str
    width: int = 1024
    height: int = 1024


class VideoRequest(BaseModel):
    prompt: str
    seed: Optional[int] = None
    duration: int = Field(default=6, ge=2, le=120)
    fps: int = Field(default=10, ge=8, le=15)
    model: str = "ltx-2"


class ChatRequest(BaseModel):
    message: str
    history: list = []
    model: str = "openai"
    system_prompt: str = "Ты VD AI — умный и дружелюбный ИИ-ассистент. Отвечай кратко и по делу."


class AuthRequest(BaseModel):
    username: str
    password: str


def _require_auth(authorization: Optional[str]):
    if not authorization:
        raise HTTPException(status_code=401, detail="No token")
    token = authorization.replace("Bearer ", "")
    user = verify_token(token)
    if not user["valid"]:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user


@app.get("/api/health")
async def health():
    return {"status": "ok", "mode": "api"}


@app.get("/api/presets")
async def get_presets():
    return ImageGenerator.get_presets()


@app.post("/api/generate/image")
async def generate_image(req: ImageRequest, authorization: Optional[str] = Header(None)):
    user = _require_auth(authorization)
    try:
        result = await asyncio.to_thread(
            image_generator.generate,
            prompt=req.prompt,
            negative_prompt=req.negative_prompt,
            width=req.width,
            height=req.height,
            guidance_scale=req.guidance_scale,
            num_inference_steps=req.num_inference_steps,
            seed=req.seed,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/generate/edit-image")
async def edit_image(req: ImageEditRequest, authorization: Optional[str] = Header(None)):
    user = _require_auth(authorization)

    try:
        image_bytes = base64.b64decode(req.image_data.split(",")[-1] if "," in req.image_data else req.image_data)

        en_prompt = req.prompt
        ru_map = {
            "черн": "black", "чёрн": "black", "чорн": "black",
            "бел": "white", "красн": "red", "син": "blue",
            "зелен": "green", "зелён": "green", "желт": "yellow",
            "сделай": "make", "добавь": "add", "убери": "remove",
            "измени": "change", "замени": "replace", "увеличь": "increase",
            "уменьши": "decrease", "ярк": "bright", "тёмн": "dark",
            "свет": "light", "цвет": "color",
            "фон": "background", "небо": "sky", "вод": "water",
            "огон": "fire", "закат": "sunset", "рассвет": "sunrise",
            "картинк": "image", "фото": "photo", "пейзаж": "landscape",
        }
        lower = req.prompt.lower()
        for ru, en in ru_map.items():
            if ru in lower:
                en_prompt = f"edit the image: {req.prompt}. Apply the effect to the ENTIRE image."
                break

        result = await _edit_with_hf(image_bytes, en_prompt, req.width, req.height)
        if result:
            return result

        result = await _edit_with_pollinations(image_bytes, en_prompt, req.width, req.height)
        if result:
            return result

        raise HTTPException(
            status_code=502,
            detail="Не удалось отредактировать. Попробуйте другой промпт."
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _edit_with_hf(image_bytes: bytes, prompt: str, width: int, height: int):
    """Edit image via Hugging Face Inference Providers (free tier: $0.10/month)"""
    try:
        import io
        from PIL import Image
        from huggingface_hub import InferenceClient

        img = Image.open(io.BytesIO(image_bytes))
        img = img.convert("RGB")
        img = img.resize((min(img.width, 1024), min(img.height, 1024)), Image.LANCZOS)

        providers = ["fal-ai", "replicate", "together"]
        model = "black-forest-labs/FLUX.1-Kontext-dev"

        for provider in providers:
            print(f"[Edit/HF] Trying {provider}/{model}...")
            try:
                client = InferenceClient(provider=provider, token=HF_TOKEN)
                result = await asyncio.to_thread(
                    client.image_to_image,
                    model=model,
                    prompt=prompt,
                    image=img,
                )

                buf = io.BytesIO()
                result.save(buf, format="PNG")
                img_bytes = buf.getvalue()

                if len(img_bytes) > 5000:
                    filename = f"edit_{uuid.uuid4().hex}.png"
                    filepath = STATIC_DIR / filename
                    with open(filepath, "wb") as f:
                        f.write(img_bytes)
                    print(f"[Edit/HF] Saved ({provider}): {filename} ({len(img_bytes)} bytes)")
                    return {"url": f"/static/generated/{filename}", "filename": filename}
                else:
                    print(f"[Edit/HF] Result too small: {len(img_bytes)} bytes")

            except Exception as e:
                print(f"[Edit/HF] Error {provider}: {e}")
                continue

        return None

    except Exception as e:
        print(f"[Edit/HF] Exception: {e}")
        return None


async def _edit_with_pollinations(image_bytes: bytes, prompt: str, width: int, height: int):
    """Edit image via media upload + GET /image/{prompt}?model=klein"""
    try:
        import io
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes))
        img = img.convert("RGB")
        img = img.resize((min(img.width, 1024), min(img.height, 1024)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90)
        clean_bytes = buf.getvalue()

        print(f"[Edit] Uploading to media...")
        upload_resp = await asyncio.to_thread(
            requests.post,
            "https://media.pollinations.ai/upload",
            headers={"Authorization": f"Bearer {POLLINATIONS_PK}"},
            files={"file": ("input.jpg", clean_bytes, "image/jpeg")},
            timeout=60
        )

        if upload_resp.status_code != 200:
            print(f"[Edit] Upload failed: {upload_resp.status_code} {upload_resp.text[:200]}")
            return None

        media_url = upload_resp.json().get("url", "")
        print(f"[Edit] Uploaded: {media_url}")

        if not media_url:
            return None

        encoded_prompt = requests.utils.quote(prompt)
        models_to_try = ["klein", "kontext"]

        for model in models_to_try:
            img_url = f"https://gen.pollinations.ai/image/{encoded_prompt}?model={model}&width={width}&height={height}&image={requests.utils.quote(media_url)}"

            print(f"[Edit] Trying GET /image with model={model}...")
            img_resp = await asyncio.to_thread(
                requests.get,
                img_url,
                headers={"Authorization": f"Bearer {POLLINATIONS_PK}"},
                timeout=120
            )

            ct = img_resp.headers.get("content-type", "none")
            print(f"[Edit] Status: {img_resp.status_code}, CT: {ct}, Size: {len(img_resp.content)}")

            if img_resp.status_code == 200 and "image" in ct and len(img_resp.content) > 5000:
                filename = f"edit_{uuid.uuid4().hex}.png"
                filepath = STATIC_DIR / filename
                with open(filepath, "wb") as f:
                    f.write(img_resp.content)
                print(f"[Edit] Saved ({model}): {filename} ({len(img_resp.content)} bytes)")
                return {"url": f"/static/generated/{filename}", "filename": filename}
            else:
                print(f"[Edit] Failed ({model}): {img_resp.text[:200]}")

        print("[Edit] All models failed")
        return None

    except Exception as e:
        print(f"[Edit] Exception: {e}")
        import traceback
        traceback.print_exc()
        return None


@app.post("/api/generate/video")
async def generate_video(req: VideoRequest, authorization: Optional[str] = Header(None)):
    user = _require_auth(authorization)
    try:
        result = await asyncio.to_thread(
            video_generator.generate_video,
            prompt=req.prompt,
            seed=req.seed,
            duration=req.duration,
            fps=req.fps,
            model=req.model,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/register")
async def api_register(req: AuthRequest):
    result = register(req.username, req.password)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/api/login")
async def api_login(req: AuthRequest):
    result = login(req.username, req.password)
    if not result["success"]:
        raise HTTPException(status_code=401, detail=result["error"])
    return result


@app.get("/api/me")
async def api_me(authorization: Optional[str] = Header(None)):
    user = _require_auth(authorization)
    return user


CHAT_MODELS = {
    "vdai": "deepseek",
    "openai": "openai",
    "llama": "llama",
    "mistral": "mistral",
}


@app.post("/api/chat")
async def chat(req: ChatRequest, authorization: Optional[str] = Header(None)):
    _require_auth(authorization)
    try:
        api_model = CHAT_MODELS.get(req.model, "deepseek")
        full_prompt = f"{req.system_prompt}\n\n"
        for msg in req.history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            full_prompt += f"{role}: {content}\n"
        full_prompt += f"user: {req.message}\nassistant:"

        resp = await asyncio.to_thread(
            requests.get,
            f"https://gen.pollinations.ai/text/{requests.utils.quote(full_prompt)}",
            params={"model": api_model, "max_tokens": 800},
            headers={"Authorization": f"Bearer {POLLINATIONS_PK}"},
            timeout=60
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"API error: {resp.text[:200]}")
        return {"reply": resp.text.strip()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/gallery")
async def api_gallery():
    try:
        files = []
        video_exts = {"mp4", "webm", "avi"}
        image_exts = {"png", "jpg", "jpeg", "gif", "webp"}
        all_exts = image_exts | video_exts

        for ext in all_exts:
            file_type = "video" if ext in video_exts else "image"
            for f in STATIC_DIR.glob(f"*.{ext}"):
                stat = f.stat()
                files.append({
                    "url": f"/static/generated/{f.name}",
                    "filename": f.name,
                    "size": stat.st_size,
                    "created": stat.st_ctime,
                    "type": file_type
                })
            for f in OUTPUT_DIR.glob(f"*.{ext}"):
                stat = f.stat()
                files.append({
                    "url": f"/outputs/{f.name}",
                    "filename": f.name,
                    "size": stat.st_size,
                    "created": stat.st_ctime,
                    "type": file_type
                })

        files.sort(key=lambda x: x["created"], reverse=True)
        seen = set()
        unique = []
        for f in files:
            if f["filename"] not in seen:
                seen.add(f["filename"])
                unique.append(f)
        return {"files": unique[:50]}
    except Exception as e:
        return {"files": [], "error": str(e)}


@app.delete("/api/gallery/{filename}")
async def api_gallery_delete(filename: str, authorization: Optional[str] = Header(None)):
    user = _require_auth(authorization)

    import re
    if not re.match(r'^[\w\-.]+$', filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    filepath = STATIC_DIR / filename
    if filepath.exists():
        filepath.unlink()
        return {"success": True, "message": "Deleted"}
    filepath = OUTPUT_DIR / filename
    if filepath.exists():
        filepath.unlink()
        return {"success": True, "message": "Deleted"}
    raise HTTPException(status_code=404, detail="File not found")


@app.get("/")
@app.get("/index.html")
async def index():
    return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.get("/style.css")
async def style():
    return FileResponse(str(FRONTEND_DIR / "style.css"))


@app.get("/app.js")
async def script():
    return FileResponse(str(FRONTEND_DIR / "app.js"))


@app.get("/favicon.ico")
async def favicon():
    return FileResponse(str(FRONTEND_DIR / "favicon.ico")) if (FRONTEND_DIR / "favicon.ico").exists() else FileResponse(str(FRONTEND_DIR / "index.html"))
