import requests
import uuid
import io
from pathlib import Path
from backend.config import OUTPUT_DIR, POLLINATIONS_PK


VIDEO_MODELS = {
    "ltx-2": "ltx-2",
    "nova-reel": "nova-reel",
    "wan": "wan",
    "wan-fast": "wan-fast",
    "veo": "veo",
    "seedance": "seedance-2.0",
}


class VideoGenerator:
    """Video generation via Pollinations /video/{prompt} API"""
    
    def generate_video(self, prompt: str, seed: int = None, duration: int = 6, fps: int = 10, model: str = "ltx-2") -> dict:
        try:
            encoded_prompt = requests.utils.quote(prompt)
            actual_seed = seed if seed and seed > 0 else (uuid.uuid4().int & 0x7fffffff)
            api_model = VIDEO_MODELS.get(model, "ltx-2")
            
            params = {
                "model": api_model,
                "width": 720,
                "height": 480,
                "seed": actual_seed,
                "duration": duration,
            }
            
            headers = {"Authorization": f"Bearer {POLLINATIONS_PK}"}
            
            print(f"[VideoGenerator] Model={api_model} | '{prompt[:50]}' | {duration}s")
            
            url = f"https://gen.pollinations.ai/video/{encoded_prompt}"
            resp = requests.get(
                url,
                params=params,
                headers=headers,
                timeout=300,
                stream=True
            )
            
            if resp.status_code == 401:
                print("[VideoGenerator] 401 with header, trying ?key= param")
                params["key"] = POLLINATIONS_PK
                resp = requests.get(
                    url,
                    params=params,
                    timeout=300,
                    stream=True
                )
            
            if resp.status_code != 200:
                print(f"[VideoGenerator] API returned {resp.status_code}, trying fallback")
                return self._fallback_gif(prompt, actual_seed, duration, fps)
            
            content_type = resp.headers.get("content-type", "")
            print(f"[VideoGenerator] Content-Type: {content_type}")
            
            if "video" not in content_type and "octet-stream" not in content_type:
                return self._fallback_gif(prompt, actual_seed, duration, fps)
            
            filename = f"vid_{uuid.uuid4().hex[:12]}.mp4"
            output_path = OUTPUT_DIR / filename
            
            with open(output_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            file_size = output_path.stat().st_size
            print(f"[VideoGenerator] Saved: {output_path} ({file_size} bytes)")
            
            if file_size < 1024:
                output_path.unlink(missing_ok=True)
                return self._fallback_gif(prompt, actual_seed, duration, fps)
            
            return {
                "filename": filename,
                "path": str(output_path),
                "url": f"/outputs/{filename}",
                "duration": duration,
                "fps": fps,
                "seed": actual_seed,
                "prompt": prompt,
                "model": api_model,
            }
            
        except Exception as e:
            print(f"[VideoGenerator] Error: {e}")
            return self._fallback_gif(prompt, seed, duration, fps)
    
    def _fallback_gif(self, prompt: str, seed: int = None, duration: int = 6, fps: int = 10) -> dict:
        """Fallback: generate keyframes and create animated GIF"""
        try:
            from PIL import Image
            
            base_seed = seed or 42
            num_keyframes = max(3, min(6, duration))
            skip = 500 // num_keyframes
            
            print(f"[VideoGenerator] GIF fallback: '{prompt[:40]}' | {num_keyframes} frames")
            
            frames = []
            for i in range(num_keyframes):
                s = base_seed + i * skip
                print(f"[VideoGenerator] Frame {i+1}/{num_keyframes} (seed={s})...")
                img = self._fetch_image(prompt, s)
                pil_img = Image.fromarray(img)
                pil_img = pil_img.resize((512, 512), Image.LANCZOS)
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
            print(f"[VideoGenerator] Saved GIF: {output_path} ({file_size} bytes)")
            
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
