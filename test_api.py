import requests
import json

url = "https://triage-ai-tan.vercel.app/triage"
payload = {
    "symptoms": "I have a very severe headache and my neck feels very stiff. I also feel nauseous.",
    "language": "English"
}
headers = {
    "Content-Type": "application/json"
}

print(f"Testing API at: {url}")
try:
    response = requests.post(url, json=payload, headers=headers, timeout=15)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        print("Response received successfully:")
        print(json.dumps(response.json(), indent=2))
    else:
        print(f"Error: {response.text}")
except Exception as e:
    print(f"An error occurred: {e}")
