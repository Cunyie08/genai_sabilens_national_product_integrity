import requests

endpoints = [
    "/api/v1/auth/login",
    "/v1/auth/login",
    "/api/consumer/scan/detect-product",
    "/consumer/scan/detect-product"
]

print("Testing direct connections to http://127.0.0.1:8000")
print("="*60)

for ep in endpoints:
    url = f"http://127.0.0.1:8000{ep}"
    try:
        if "login" in ep:
            res = requests.post(url, json={"phone": "9187654321", "password": "tegafresh12345*"})
        else:
            res = requests.post(url, json={"image_data": "dummy"})
        print(f"[{res.status_code}] {url}")
        print(f"Response: {res.text[:100]}")
    except requests.exceptions.ConnectionError:
        print(f"[CONNECTION REFUSED] {url}")
    except Exception as e:
        print(f"[ERROR] {url}: {str(e)}")
