import sys, os
sys.path.insert(0, "C:\\Users\\Вадим\\Desktop\\VD AI")
os.chdir("C:\\Users\\Вадим\\Desktop\\VD AI")
from backend.models.video_generator import VideoGenerator
gen = VideoGenerator()
r = gen.generate_video("самолёт летит в здание", seed=42, duration=5, fps=5)
print("OK:", r["filename"])
