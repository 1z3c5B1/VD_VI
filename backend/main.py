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
from backend.config import OUTPUT_DIR, STATIC_DIR, BASE_DIR, POLLINATIONS_KEY
from backend.auth import register, login, verify_token

image_generator = ImageGenerator()
video_generator = VideoGenerator()

app = FastAPI(title="VD AI - Генератор изображений и видео")

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
    duration: int = Field(default=6, ge=4, le=25)
    fps: int = Field(default=10, ge=5, le=30)


class ChatRequest(BaseModel):
    message: str
    history: list = []
    model: str = "openai"
    system_prompt: str = "Ты VD AI — умный и дружелюбный ИИ-ассистент. Отвечай кратко и по делу."


class AuthRequest(BaseModel):
    username: str
    password: str


@app.get("/api/health")
async def health():
    return {"status": "ok", "mode": "api"}


@app.get("/api/presets")
async def get_presets():
    return ImageGenerator.get_presets()


@app.post("/api/generate/image")
async def generate_image(req: ImageRequest):
    try:
        result = image_generator.generate(
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
async def edit_image(req: ImageEditRequest):
    try:
        import base64, uuid
        # Decode base64 image
        image_bytes = base64.b64decode(req.image_data.split(",")[-1] if "," in req.image_data else req.image_data)
        ext = "png"
        if req.image_data.startswith("data:image/jpeg"):
            ext = "jpg"
        elif req.image_data.startswith("data:image/webp"):
            ext = "webp"

        temp_path = STATIC_DIR / f"edit_input_{uuid.uuid4().hex}.{ext}"
        with open(temp_path, "wb") as f:
            f.write(image_bytes)

        poll_headers = {"Authorization": f"Bearer {POLLINATIONS_KEY}"}
        with open(temp_path, "rb") as f:
            resp = requests.post(
                "https://gen.pollinations.ai/v1/images/edits",
                headers=poll_headers,
                files={"image": (f"input.{ext}", f, f"image/{ext}")},
                data={"prompt": req.prompt, "n": 1, "size": f"{req.width}x{req.height}"},
                timeout=120
            )

        temp_path.unlink(missing_ok=True)

        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Edit API error: {resp.text[:200]}")

        data = resp.json()
        b64 = data["data"][0]["b64_json"]
        filename = f"edit_{uuid.uuid4().hex}.png"
        filepath = STATIC_DIR / filename
        with open(filepath, "wb") as f:
            f.write(base64.b64decode(b64))

        return {"url": f"/static/generated/{filename}", "filename": filename}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/generate/video")
async def generate_video(req: VideoRequest):
    try:
        result = video_generator.generate_video(
            prompt=req.prompt,
            seed=req.seed,
            duration=req.duration,
            fps=req.fps,
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
    if not authorization:
        raise HTTPException(status_code=401, detail="No token")
    token = authorization.replace("Bearer ", "")
    result = verify_token(token)
    if not result["valid"]:
        raise HTTPException(status_code=401, detail="Invalid token")
    return result


CHAT_MODELS = {
    "vdai": "deepseek",
    "openai": "openai",
    "llama": "llama",
    "mistral": "mistral",
}

@app.post("/api/chat")
async def chat(req: ChatRequest):
    try:
        api_model = CHAT_MODELS.get(req.model, "deepseek")
        full_prompt = f"{req.system_prompt}\n\n"
        for msg in req.history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            full_prompt += f"{role}: {content}\n"
        full_prompt += f"user: {req.message}\nassistant:"

        resp = requests.get(
            f"https://gen.pollinations.ai/text/{requests.utils.quote(full_prompt)}",
            params={"model": api_model, "max_tokens": 800},
            headers={"Authorization": f"Bearer {POLLINATIONS_KEY}"},
            timeout=60
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"API error: {resp.text[:200]}")
        return {"reply": resp.text.strip()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/gallery")
async def api_gallery():
    try:
        files = []
        for ext in ["png", "jpg", "jpeg", "gif", "webp", "mp4"]:
            for f in STATIC_DIR.glob(f"*.{ext}"):
                stat = f.stat()
                files.append({
                    "url": f"/static/generated/{f.name}",
                    "filename": f.name,
                    "size": stat.st_size,
                    "created": stat.st_ctime,
                    "type": "video" if ext == "mp4" else "image"
                })
        files.sort(key=lambda x: x["created"], reverse=True)
        return {"files": files[:50]}
    except Exception as e:
        return {"files": [], "error": str(e)}


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
