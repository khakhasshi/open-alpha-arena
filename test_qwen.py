import requests
import json
import os

api_key = os.getenv("QWEN_API_KEY", "your-key-here")
base_url = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"

print(f"Testing Qwen API with key: {api_key[:10] if api_key else 'None'}...")

url = f"{base_url}/chat/completions"
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {api_key}"
}
data = {
    "model": "qwen-plus",
    "messages": [
        {"role": "user", "content": "Hello, are you working?"}
    ]
}

try:
    response = requests.post(url, headers=headers, json=data, timeout=10)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        print("Response:", response.json()['choices'][0]['message']['content'])
        print("\n✅ Qwen API Test Passed!")
    else:
        print("Response:", response.text)
        print("\n❌ Qwen API Test Failed!")
except Exception as e:
    print(f"\n❌ Error: {e}")
