import requests
import uuid
import io
from pathlib import Path
from backend.config import OUTPUT_DIR, POLLINATIONS_KEY, POLLINATIONS_PK


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
    
    def generate_video(self, prompt: str, seed: int = None, duration: int = 6, fps: int = 10, model: str = "wan") -> dict:
        try:
            encoded_prompt = requests.utils.quote(prompt)
            actual_seed = seed if seed and seed > 0 else (uuid.uuid4().int & 0x7fffffff)
            api_model = VIDEO_MODELS.get(model, "wan")
            
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
                return self._fallback_motion(prompt, actual_seed, duration, fps)
            
            content_type = resp.headers.get("content-type", "")
            print(f"[VideoGenerator] Content-Type: {content_type}")
            
            if "video" not in content_type and "octet-stream" not in content_type:
                text = resp.text[:200] if hasattr(resp, 'text') else ""
                print(f"[VideoGenerator] Not video content: {text}")
                return self._fallback_motion(prompt, actual_seed, duration, fps)
            
            filename = f"vid_{uuid.uuid4().hex[:12]}.mp4"
            output_path = OUTPUT_DIR / filename
            
            with open(output_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            file_size = output_path.stat().st_size
            print(f"[VideoGenerator] Saved: {output_path} ({file_size} bytes)")
            
            if file_size < 1024:
                print("[VideoGenerator] File too small, likely error. Using fallback")
                output_path.unlink(missing_ok=True)
                return self._fallback_motion(prompt, actual_seed, duration, fps)
            
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
            return self._fallback_motion(prompt, seed, duration, fps)
    
    def _fallback_motion(self, prompt: str, seed: int = None, duration: int = 6, fps: int = 10) -> dict:
        """Fallback: generate ONE image and create smooth motion effects (zoom, pan)"""
        try:
            import cv2
            import numpy as np
            from PIL import Image
            
            base_seed = seed or 42
            total = duration * fps
            
            print(f"[VideoGenerator] Motion fallback: '{prompt[:40]}' | {duration}s | {fps}FPS")
            
            print("[VideoGenerator] Generating base image...")
            img = self._fetch_image(prompt, base_seed)
            h, w = img.shape[:2]
            
            filename = f"vid_{uuid.uuid4().hex[:12]}.mp4"
            output_path = OUTPUT_DIR / filename
            
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            out = cv2.VideoWriter(str(output_path), fourcc, fps, (w, h))
            
            effect = base_seed % 4
            
            if effect == 0:
                name = "slow zoom in"
                for i in range(total):
                    t = i / total
                    scale = 1.0 + t * 0.15
                    frame = self._zoom(img, scale)
                    out.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
            elif effect == 1:
                name = "slow zoom out"
                for i in range(total):
                    t = i / total
                    scale = 1.15 - t * 0.15
                    frame = self._zoom(img, scale)
                    out.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
            elif effect == 2:
                name = "pan left"
                for i in range(total):
                    t = i / total
                    dx = int(t * w * 0.1)
                    frame = self._pan(img, dx, 0)
                    out.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
            else:
                name = "pan right"
                for i in range(total):
                    t = i / total
                    dx = int(-t * w * 0.1)
                    frame = self._pan(img, dx, 0)
                    out.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
            
            out.release()
            print(f"[VideoGenerator] Saved motion ({name}): {output_path}")
            
            return {
                "filename": filename,
                "path": str(output_path),
                "url": f"/outputs/{filename}",
                "frames": total,
                "fps": fps,
                "duration": duration,
                "seed": base_seed,
                "prompt": prompt,
                "model": f"motion-{name}",
            }
            
        except Exception as e:
            raise RuntimeError(f"Video generation failed: {e}")
    
    def _zoom(self, img, scale: float):
        """Zoom into center of image"""
        import cv2
        h, w = img.shape[:2]
        new_w = int(w * scale)
        new_h = int(h * scale)
        
        resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        
        x1 = (new_w - w) // 2
        y1 = (new_h - h) // 2
        
        x1 = max(0, min(x1, new_w - w))
        y1 = max(0, min(y1, new_h - h))
        
        frame = resized[y1:y1+h, x1:x1+w]
        
        if frame.shape[0] != h or frame.shape[1] != w:
            frame = cv2.resize(frame, (w, h))
        
        return frame
    
    def _pan(self, img, dx: int, dy: int):
        """Pan image by dx, dy pixels"""
        import cv2
        import numpy as np
        h, w = img.shape[:2]
        M = np.float32([[1, 0, dx], [0, 1, dy]])
        frame = cv2.warpAffine(img, M, (w, h), borderMode=cv2.BORDER_REFLECT)
        return frame
    
    def _fetch_image(self, prompt: str, seed: int):
        import numpy as np
        from PIL import Image
        
        encoded = requests.utils.quote(prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=768&seed={seed}&model=flux"
        resp = requests.get(url, timeout=120)
        if resp.status_code != 200:
            raise RuntimeError(f"Image failed: {resp.status_code}")
        img = Image.open(io.BytesIO(resp.content))
        return np.array(img.convert("RGB"))
