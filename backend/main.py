import os
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
from backend.auth import (
    register, login, verify_token, deduct_coins, use_promo_code, is_admin, admin_login,
    admin_get_users, admin_get_promos, admin_create_promo, admin_delete_promo,
    admin_ban_user, admin_unban_user, admin_set_coins, admin_toggle_pro, admin_delete_user,
)

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


class PromoRequest(BaseModel):
    code: str


class AdminPromoRequest(BaseModel):
    code: str
    type: str
    value: int = 0
    duration: str = ""


class AdminCoinsRequest(BaseModel):
    user_id: int
    coins: int


class AdminBanRequest(BaseModel):
    reason: str = ""


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
        coin_result = deduct_coins(user["user_id"], 1)
        if not coin_result["success"]:
            raise HTTPException(status_code=402, detail=coin_result["error"])
        
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
        result["coins"] = coin_result.get("coins", 0)
        result["unlimited"] = coin_result.get("unlimited", False)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/generate/edit-image")
async def edit_image(req: ImageEditRequest, authorization: Optional[str] = Header(None)):
    user = _require_auth(authorization)

    try:
        coin_result = deduct_coins(user["user_id"], 2)
        if not coin_result["success"]:
            raise HTTPException(status_code=402, detail=coin_result["error"])
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
            result["coins"] = coin_result.get("coins", 0)
            result["unlimited"] = coin_result.get("unlimited", False)
            return result

        result = await _edit_with_pollinations(image_bytes, en_prompt, req.width, req.height)
        if result:
            result["coins"] = coin_result.get("coins", 0)
            result["unlimited"] = coin_result.get("unlimited", False)
            return result

        deduct_coins(user["user_id"], -2)
        raise HTTPException(
            status_code=502,
            detail="Не удалось отредактировать. Попробуйте другой промпт."
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _edit_with_hf(image_bytes: bytes, prompt: str, width: int, height: int):
    """Edit image via Pollinations free GET API (klein model)"""
    try:
        import io
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes))
        img = img.convert("RGB")
        img = img.resize((min(img.width, 1024), min(img.height, 1024)), Image.LANCZOS)

        tmp_filename = f"tmp_{uuid.uuid4().hex[:8]}.jpg"
        tmp_path = STATIC_DIR / tmp_filename
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        with open(tmp_path, "wb") as f:
            f.write(buf.getvalue())

        from backend.config import OUTPUT_DIR
        host = os.environ.get("RENDER_EXTERNAL_URL", "https://vd-ai.onrender.com")
        image_url = f"{host}/static/generated/{tmp_filename}"
        print(f"[Edit] Local image URL: {image_url}")

        encoded_prompt = requests.utils.quote(prompt)
        edit_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?model=klein&image={image_url}&width={width}&height={height}&seed={int(uuid.uuid4().int % 999999)}"

        print(f"[Edit] Requesting: {edit_url[:150]}...")
        resp = await asyncio.to_thread(
            requests.get,
            edit_url,
            timeout=120,
        )

        print(f"[Edit] Status: {resp.status_code}, CT: {resp.headers.get('content-type', '?')}, Size: {len(resp.content)}")

        try:
            os.remove(str(tmp_path))
        except Exception:
            pass

        if resp.status_code == 200 and "image" in resp.headers.get("content-type", ""):
            result_img = Image.open(io.BytesIO(resp.content))
            if result_img.size[0] > 10 and result_img.size[1] > 10:
                out_buf = io.BytesIO()
                result_img.save(out_buf, format="PNG")
                img_bytes = out_buf.getvalue()

                if len(img_bytes) > 5000:
                    filename = f"edit_{uuid.uuid4().hex}.png"
                    filepath = STATIC_DIR / filename
                    with open(filepath, "wb") as f:
                        f.write(img_bytes)
                    print(f"[Edit] Saved: {filename} ({len(img_bytes)} bytes)")
                    return {"url": f"/static/generated/{filename}", "filename": filename}

        print(f"[Edit] Failed: {resp.status_code}")
        return None

    except Exception as e:
        print(f"[Edit] Exception: {e}")
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
    "vdai": "openai",
    "openai": "openai",
}

CHAT_PERSONAS = {
    "vdai": "Ты VDAI — умный, дружелюбный ИИ-ассистент. Отвечай на русском языке, будь полезным и конкретным. Не используй эмодзи.",
    "openai": "You are a helpful AI assistant. Answer concisely and accurately.",
    "claude": "You are Claude, an AI assistant made by Anthropic. Be helpful, harmless, and honest. Answer concisely.",
    "mistral": "You are Mistral, a helpful AI assistant. Answer concisely and accurately in the user's language.",
    "gemini": "You are Gemini, Google's AI assistant. Be helpful and concise. Answer in the user's language.",
    "llama": "You are Llama, Meta's open-source AI assistant. Be helpful and concise. Answer in the user's language.",
}


FREE_CHAT_MODELS = {"vdai"}


@app.post("/api/chat")
async def chat(req: ChatRequest, authorization: Optional[str] = Header(None)):
    user = _require_auth(authorization)
    user_id = user["user_id"]
    is_pro = user.get("pro", 0)

    if req.model not in FREE_CHAT_MODELS and not is_pro:
        raise HTTPException(status_code=403, detail="Эта модель доступна только для PRO. Купи PRO или используй VDAI.")

    result = deduct_coins(user_id, 1)
    if not result["success"]:
        raise HTTPException(status_code=402, detail=result["error"])

    try:
        api_model = CHAT_MODELS.get(req.model, "openai")
        system_prompt = CHAT_PERSONAS.get(req.model, req.system_prompt)

        messages = [{"role": "system", "content": system_prompt}]
        for msg in req.history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": req.message})

        print(f"[Chat] Model={req.model} -> API={api_model}, msgs={len(messages)}")

        payload = {
            "model": api_model,
            "messages": messages,
            "stream": False,
        }

        try:
            resp = await asyncio.to_thread(
                requests.post,
                "https://text.pollinations.ai/openai",
                json=payload,
                timeout=45,
            )
        except requests.Timeout:
            print("[Chat] Timeout, retrying...")
            resp = await asyncio.to_thread(
                requests.post,
                "https://text.pollinations.ai/openai",
                json=payload,
                timeout=45,
            )

        if resp.status_code != 200:
            print(f"[Chat] Error {resp.status_code}: {resp.text[:200]}")
            raise HTTPException(status_code=502, detail=f"Ошибка чата. Попробуй позже.")

        data = resp.json()
        reply = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        if not reply:
            raise HTTPException(status_code=502, detail="Пустой ответ от модели")

        return {"reply": reply, "coins": result.get("coins", 0)}
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


@app.post("/api/admin/auth")
async def api_admin_auth(req: PromoRequest, authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="No token")
    token = authorization.replace("Bearer ", "")
    result = admin_login(token, req.code)
    if not result["success"]:
        raise HTTPException(status_code=403, detail=result["error"])
    return result


@app.post("/api/promo")
async def api_activate_promo(req: PromoRequest, authorization: Optional[str] = Header(None)):
    user = _require_auth(authorization)
    result = use_promo_code(req.code.upper(), user["user_id"])
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.get("/api/admin/users")
async def api_admin_users(authorization: Optional[str] = Header(None)):
    token = authorization.replace("Bearer ", "") if authorization else ""
    result = admin_get_users(token)
    if not result["success"]:
        raise HTTPException(status_code=403, detail=result["error"])
    return result


@app.get("/api/admin/promos")
async def api_admin_promos(authorization: Optional[str] = Header(None)):
    token = authorization.replace("Bearer ", "") if authorization else ""
    result = admin_get_promos(token)
    if not result["success"]:
        raise HTTPException(status_code=403, detail=result["error"])
    return result


@app.post("/api/admin/promo")
async def api_admin_create_promo(req: AdminPromoRequest, authorization: Optional[str] = Header(None)):
    token = authorization.replace("Bearer ", "") if authorization else ""
    result = admin_create_promo(token, req.code, req.type, req.value, req.duration)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.delete("/api/admin/promo/{code}")
async def api_admin_delete_promo(code: str, authorization: Optional[str] = Header(None)):
    token = authorization.replace("Bearer ", "") if authorization else ""
    result = admin_delete_promo(token, code)
    if not result["success"]:
        raise HTTPException(status_code=403, detail=result["error"])
    return result


@app.post("/api/admin/ban/{user_id}")
async def api_admin_ban(user_id: int, req: AdminBanRequest = None, authorization: Optional[str] = Header(None)):
    token = authorization.replace("Bearer ", "") if authorization else ""
    reason = req.reason if req else ""
    result = admin_ban_user(token, user_id, reason)
    if not result["success"]:
        raise HTTPException(status_code=403, detail=result["error"])
    return result


@app.post("/api/admin/unban/{user_id}")
async def api_admin_unban(user_id: int, authorization: Optional[str] = Header(None)):
    token = authorization.replace("Bearer ", "") if authorization else ""
    result = admin_unban_user(token, user_id)
    if not result["success"]:
        raise HTTPException(status_code=403, detail=result["error"])
    return result


@app.post("/api/admin/coins")
async def api_admin_set_coins(req: AdminCoinsRequest, authorization: Optional[str] = Header(None)):
    token = authorization.replace("Bearer ", "") if authorization else ""
    result = admin_set_coins(token, req.user_id, req.coins)
    if not result["success"]:
        raise HTTPException(status_code=403, detail=result["error"])
    return result


@app.post("/api/admin/pro/{user_id}")
async def api_admin_toggle_pro(user_id: int, authorization: Optional[str] = Header(None)):
    token = authorization.replace("Bearer ", "") if authorization else ""
    result = admin_toggle_pro(token, user_id)
    if not result["success"]:
        raise HTTPException(status_code=403, detail=result["error"])
    return result


@app.delete("/api/admin/user/{user_id}")
async def api_admin_delete_user(user_id: int, authorization: Optional[str] = Header(None)):
    token = authorization.replace("Bearer ", "") if authorization else ""
    result = admin_delete_user(token, user_id)
    if not result["success"]:
        raise HTTPException(status_code=403, detail=result["error"])
    return result


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
