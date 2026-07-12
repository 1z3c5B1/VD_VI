import requests

# Try old pollinations.ai video endpoint (free?)
url = "https://pollinations.ai/p/plane%20flying%20through%20the%20sky.mp4"
print(f"Testing: {url}")
resp = requests.get(url, timeout=60)
print(f"Status: {resp.status_code}, Size: {len(resp.content)}b, Type: {resp.headers.get('content-type', '?')[:40]}")
if len(resp.content) > 1000:
    with open("outputs/test_free.mp4", "wb") as f:
        f.write(resp.content)
    print("Saved!")
