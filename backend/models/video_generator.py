import requests
import uuid
import io
import base64
from pathlib import Path
from backend.config import OUTPUT_DIR, POLLINATIONS_PK, VIDEO_API_URL


VIDEO_MODELS = {
    "ltx-2": "ltx-2",
    "nova-reel": "nova-reel",
    "wan": "wan",
    "wan-fast": "wan-fast",
    "veo": "veo",
    "seedance": "seedance-2.0",
}


class VideoGenerator:
    """Video generation: Colab API → Pollinations → GIF fallback"""

    def generate_video(self, prompt: str, seed: int = None, duration: int = 6, fps: int = 10, model: str = "ltx-2", image_b64: str = None) -> dict:
        actual_seed = seed if seed and seed > 0 else (uuid.uuid4().int & 0x7fffffff)

        if VIDEO_API_URL:
            try:
                return self._colab_api(prompt, actual_seed, duration, image_b64)
            except Exception as e:
                print(f"[VideoGenerator] Colab API failed: {e}, falling back")

        try:
            return self._pollinations_api(prompt, actual_seed, duration, fps, model)
        except Exception as e:
            print(f"[VideoGenerator] Pollinations failed: {e}, using GIF fallback")

        return self._fallback_gif(prompt, actual_seed, duration, fps, image_b64)

    def _colab_api(self, prompt: str, seed: int, duration: int, image_b64: str = None) -> dict:
        import time
        print(f"[VideoGenerator] Colab API: '{prompt[:50]}' | img={'yes' if image_b64 else 'no'}")

        if image_b64:
            endpoint = f"{VIDEO_API_URL}/generate/image-to-video"
            body = {"prompt": prompt, "image": image_b64}
        else:
            endpoint = f"{VIDEO_API_URL}/generate/text-to-video"
            body = {"prompt": prompt, "num_frames": min(duration * 8, 49)}

        resp = requests.post(endpoint, json=body, timeout=600)
        if resp.status_code != 200:
            raise RuntimeError(f"Colab returned {resp.status_code}: {resp.text[:200]}")

        data = resp.json()
        if not data.get("success"):
            raise RuntimeError(data.get("error", "Colab failed"))

        video_url = f"{VIDEO_API_URL}{data['download_url']}"
        vid_resp = requests.get(video_url, timeout=120)
        if vid_resp.status_code != 200:
            raise RuntimeError(f"Download failed: {vid_resp.status_code}")

        filename = f"vid_{uuid.uuid4().hex[:12]}.mp4"
        output_path = OUTPUT_DIR / filename
        with open(output_path, "wb") as f:
            f.write(vid_resp.content)

        file_size = output_path.stat().st_size
        print(f"[VideoGenerator] Colab MP4 saved: {filename} ({file_size} bytes)")

        if file_size < 1024:
            output_path.unlink(missing_ok=True)
            raise RuntimeError("Generated file too small")

        return {
            "filename": filename,
            "path": str(output_path),
            "url": f"/outputs/{filename}",
            "duration": duration,
            "fps": fps,
            "seed": seed,
            "prompt": prompt,
            "model": "cogvideox-2b",
        }

    def _pollinations_api(self, prompt: str, seed: int, duration: int, fps: int, model: str) -> dict:
        import requests.utils
        encoded_prompt = requests.utils.quote(prompt)
        api_model = VIDEO_MODELS.get(model, "ltx-2")

        params = {
            "model": api_model,
            "width": 720,
            "height": 480,
            "seed": seed,
            "duration": duration,
        }

        headers = {"Authorization": f"Bearer {POLLINATIONS_PK}"}
        print(f"[VideoGenerator] Pollinations: Model={api_model} | '{prompt[:50]}' | {duration}s")

        url = f"https://gen.pollinations.ai/video/{encoded_prompt}"
        resp = requests.get(url, params=params, headers=headers, timeout=300, stream=True)

        if resp.status_code == 401:
            params["key"] = POLLINATIONS_PK
            resp = requests.get(url, params=params, timeout=300, stream=True)

        if resp.status_code != 200:
            raise RuntimeError(f"API returned {resp.status_code}")

        content_type = resp.headers.get("content-type", "")
        if "video" not in content_type and "octet-stream" not in content_type:
            raise RuntimeError(f"Not video: {content_type}")

        filename = f"vid_{uuid.uuid4().hex[:12]}.mp4"
        output_path = OUTPUT_DIR / filename
        with open(output_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        file_size = output_path.stat().st_size
        if file_size < 1024:
            output_path.unlink(missing_ok=True)
            raise RuntimeError("File too small")

        return {
            "filename": filename,
            "path": str(output_path),
            "url": f"/outputs/{filename}",
            "duration": duration,
            "fps": fps,
            "seed": seed,
            "prompt": prompt,
            "model": api_model,
        }

    def _fallback_gif(self, prompt: str, seed: int = None, duration: int = 6, fps: int = 10, image_b64: str = None) -> dict:
        try:
            from PIL import Image, ImageFilter

            base_seed = seed or 42
            num_keyframes = max(4, min(8, duration * 2))
            skip = 300 // num_keyframes

            print(f"[VideoGenerator] GIF fallback: '{prompt[:40]}' | {num_keyframes} frames")

            if image_b64:
                img_bytes = base64.b64decode(image_b64)
                base_img = Image.open(io.BytesIO(img_bytes)).convert("RGB").resize((512, 512))
                frames = [base_img]
                for i in range(1, num_keyframes):
                    s = base_seed + i * skip
                    img = self._fetch_image(prompt + f" frame {i}", s)
                    pil_img = Image.fromarray(img).resize((512, 512))
                    blended = Image.blend(frames[-1], pil_img, 0.5)
                    blended = blended.filter(ImageFilter.SMOOTH)
                    frames.append(blended)
            else:
                frames = []
                for i in range(num_keyframes):
                    s = base_seed + i * skip
                    print(f"[VideoGenerator] Frame {i+1}/{num_keyframes} (seed={s})...")
                    img = self._fetch_image(prompt, s)
                    pil_img = Image.fromarray(img).resize((512, 512))
                    if frames:
                        blended = Image.blend(frames[-1], pil_img, 0.6)
                        blended = blended.filter(ImageFilter.SMOOTH)
                        frames.append(blended)
                    else:
                        frames.append(pil_img)

            filename = f"vid_{uuid.uuid4().hex[:12]}.gif"
            output_path = OUTPUT_DIR / filename

            frame_duration = int(1000 / fps)
            frames[0].save(
                str(output_path),
                save_all=True,
                append_images=frames[1:],
                duration=frame_duration,
                loop=0,
                optimize=True,
            )

            file_size = output_path.stat().st_size
            print(f"[VideoGenerator] Saved GIF: {filename} ({file_size} bytes)")

            return {
                "filename": filename,
                "path": str(output_path),
                "url": f"/outputs/{filename}",
                "duration": duration,
                "fps": fps,
                "seed": base_seed,
                "prompt": prompt,
                "model": "gif-fallback",
            }

        except Exception as e:
            raise RuntimeError(f"Video generation failed: {e}")

    def _fetch_image(self, prompt: str, seed: int):
        import numpy as np
        from PIL import Image

        encoded = requests.utils.quote(prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded}?width=512&height=512&seed={seed}&model=flux"
        resp = requests.get(url, timeout=120)
        if resp.status_code != 200:
            raise RuntimeError(f"Image failed: {resp.status_code}")
        img = Image.open(io.BytesIO(resp.content))
        return np.array(img.convert("RGB"))
