import io
import uuid
import requests
from PIL import Image
from pathlib import Path
from backend.config import OUTPUT_DIR


API_URL = "https://image.pollinations.ai/prompt"


class ImageGenerator:
    def generate(
        self,
        prompt: str,
        negative_prompt: str = None,
        width: int = 1024,
        height: int = 1024,
        guidance_scale: float = 7.5,
        num_inference_steps: int = 25,
        seed: int = None,
    ) -> dict:
        import json

        print(f"[ImageGenerator] Pollinations: '{prompt[:50]}...'")

        import random
        encoded = requests.utils.quote(prompt)
        actual_seed = random.randint(1, 999999) if not seed or seed == 0 else seed
        url = f"{API_URL}/{encoded}?width={width}&height={height}&seed={actual_seed}&model=flux"

        print(f"[ImageGenerator] Requesting: {url}")
        response = requests.get(url, timeout=120)

        if response.status_code != 200:
            raise RuntimeError(f"API error ({response.status_code})")

        image = Image.open(io.BytesIO(response.content))

        filename = f"img_{uuid.uuid4().hex[:12]}.png"
        output_path = OUTPUT_DIR / filename
        image.save(output_path)
        print(f"[ImageGenerator] Saved: {output_path} ({image.size})")

        return {
            "filename": filename,
            "path": str(output_path),
            "url": f"/outputs/{filename}",
            "seed": actual_seed,
            "prompt": prompt,
        }

    @staticmethod
    def get_presets():
        return {
            "sizes": [
                {"label": "Square (1024x1024)", "width": 1024, "height": 1024},
                {"label": "Portrait (1024x1536)", "width": 1024, "height": 1536},
                {"label": "Landscape (1536x1024)", "width": 1536, "height": 1024},
                {"label": "Small (768x768)", "width": 768, "height": 768},
            ],
            "styles": [
                "cinematic", "anime", "photorealistic", "fantasy art",
                "oil painting", "3D render", "pixel art", "sketch",
            ],
        }
