import requests

headers = {"Authorization": "Bearer sk_TxyHaOVGAzdSY8FIk1bRoAN6dA47TBuO"}

# Check account balance via text endpoint
resp = requests.get("https://gen.pollinations.ai/v1/models", headers=headers, timeout=15)
print(f"Models: {resp.status_code}")

models = resp.json().get("data", [])
for m in models:
    mid = m.get("id", "")
    if any(v in mid.lower() for v in ["video", "ltx", "nova", "veo", "wan", "seedance", "grok"]):
        print(f"  Video model: {mid}")

# Try the text endpoint which might be free
print("\n--- Testing free text endpoint ---")
resp = requests.get("https://gen.pollinations.ai/text/hello?model=openai", headers=headers, timeout=30)
print(f"Text: {resp.status_code}, {len(resp.content)}b")
if len(resp.content) < 500:
    print(f"  Body: {resp.content[:200]}")
else:
    print(f"  OK - got response")
