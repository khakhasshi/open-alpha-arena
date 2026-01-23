import requests
import json
import os

# Configuration from backend/main.py
api_key = os.getenv("OPENAI_API_KEY", "your-key-here")
base_url = "https://api.openai.com/v1"
model = "gpt-3.5-turbo"

print(f"Testing GPT API ({base_url}) with key: {api_key[:10]}...")

url = f"{base_url}/chat/completions"
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {api_key}"
}
data = {
    "model": model,
    "messages": [
        {"role": "user", "content": "Hello, are you working?"}
    ],
    "max_tokens": 10
}

try:
    response = requests.post(url, headers=headers, json=data, timeout=10)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        content = response.json()['choices'][0]['message']['content']
        print("Response:", content)
        print("\n✅ GPT API Test Passed!")
    else:
        print("Response:", response.text)
        print("\n❌ GPT API Test Failed!")
except Exception as e:
    print(f"\n❌ Error: {e}")
