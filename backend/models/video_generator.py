import io
import uuid
import cv2
import numpy as np
import requests
from PIL import Image
from pathlib import Path
from backend.config import OUTPUT_DIR

API = "https://image.pollinations.ai/prompt"


class VideoGenerator:
    def _fetch_image(self, prompt: str, seed: int) -> np.ndarray:
        encoded = requests.utils.quote(prompt)
        url = f"{API}/{encoded}?width=512&height=512&seed={seed}&model=flux"
        resp = requests.get(url, timeout=120)
        if resp.status_code != 200:
            raise RuntimeError(f"Image failed: {resp.status_code}")
        img = Image.open(io.BytesIO(resp.content))
        return np.array(img.convert("RGB"))

    def _morph(self, a: np.ndarray, b: np.ndarray, t: float) -> np.ndarray:
        ga = cv2.cvtColor(a, cv2.COLOR_RGB2GRAY)
        gb = cv2.cvtColor(b, cv2.COLOR_RGB2GRAY)

        flow = cv2.calcOpticalFlowFarneback(ga, gb, None, 0.5, 3, 15, 3, 5, 1.2, 0)
        h, w = flow.shape[:2]
        y, x = np.mgrid[0:h, 0:w].astype(np.float32)
        fx = x + flow[:, :, 0] * t
        fy = y + flow[:, :, 1] * t
        fx = np.clip(fx, 0, w - 1)
        fy = np.clip(fy, 0, h - 1)

        warped = cv2.remap(a, fx, fy, cv2.INTER_LINEAR)
        blended = cv2.addWeighted(warped, 1 - t, b, t, 0)
        return blended.astype(np.uint8)

    def generate_video(self, prompt: str, seed: int = None, duration: int = 6, fps: int = 10) -> dict:
        total = duration * fps
        base_seed = seed or 42
        num_keyframes = max(3, min(6, duration))
        skip = 500 // num_keyframes

        print(f"[VideoGenerator] '{prompt[:40]}' | {duration}s | {fps}FPS | {num_keyframes} keyframes")

        keyframes = []
        for i in range(num_keyframes):
            s = base_seed + i * skip
            print(f"[VideoGenerator] Keyframe {i+1}/{num_keyframes} (seed={s})...")
            keyframes.append(self._fetch_image(prompt, s))

        filename = f"vid_{uuid.uuid4().hex[:12]}.mp4"
        output_path = OUTPUT_DIR / filename
        h, w = keyframes[0].shape[:2]
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(str(output_path), fourcc, fps, (w, h))

        frames_per_seg = total // (num_keyframes - 1)

        for seg in range(num_keyframes - 1):
            a = keyframes[seg]
            b = keyframes[seg + 1]
            for i in range(frames_per_seg):
                t = i / frames_per_seg
                frame = self._morph(a, b, t)
                out.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))

        out.release()
        print(f"[VideoGenerator] Saved: {output_path}")
        return {
            "filename": filename,
            "path": str(output_path),
            "url": f"/outputs/{filename}",
            "frames": total,
            "fps": fps,
            "duration": duration,
            "seed": base_seed,
            "prompt": prompt,
        }
