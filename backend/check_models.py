import os
import json
import urllib.request
import urllib.error
from dotenv import load_dotenv

load_dotenv()
key = os.getenv("GROQ_API_KEY")
print("Key length:", len(key) if key else 0)
print("Key starts with:", key[:6] if key else None)

req = urllib.request.Request(
    "https://api.groq.com/openai/v1/models",
    headers={"Authorization": f"Bearer {key}"}
)

try:
    with urllib.request.urlopen(req) as response:
        print("Status code:", response.status)
        data = json.loads(response.read())
        for m in data.get("data", []):
            print(m["id"])
except urllib.error.HTTPError as e:
    print("HTTP Error:", e.code)
    print("Body:", e.read().decode())