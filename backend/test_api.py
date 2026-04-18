"""Smoke test for TerraApp backend API."""
import urllib.request
import json

BASE = "http://localhost:8000"

def req(method, path, token=None, body=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body else None
    r = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(r)
        return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())

def test():
    print("=== TerraApp API Smoke Test ===\n")

    # Health
    code, data = req("GET", "/health")
    assert code == 200 and data["status"] == "ok", f"Health failed: {data}"
    print(f"[OK] GET /health -> {data}")

    # Auth: Login
    code, data = req("POST", "/api/v1/auth/login", body={"login": "admin", "password": "admin123"})
    assert code == 200, f"Login failed: {data}"
    token = data["access_token"]
    print(f"[OK] POST /api/v1/auth/login -> role={data['role']}, user_id={data['user_id']}")

    # Users: /me
    code, data = req("GET", "/api/v1/users/me", token=token)
    assert code == 200, f"/me failed: {data}"
    print(f"[OK] GET /api/v1/users/me -> {data['full_name']} (id={data['id']})")

    # Users: list (admin only)
    code, data = req("GET", "/api/v1/users", token=token)
    assert code == 200, f"/users failed: {data}"
    print(f"[OK] GET /api/v1/users -> {len(data)} users")

    # Dictionaries
    code, data = req("GET", "/api/v1/dictionaries/activities", token=token)
    assert code == 200, f"/dict/activities failed: {data}"
    print(f"[OK] GET /api/v1/dictionaries/activities -> {len(data)} items")

    code, data = req("GET", "/api/v1/dictionaries/locations", token=token)
    assert code == 200
    print(f"[OK] GET /api/v1/dictionaries/locations -> {len(data)} items")

    # Reports
    code, data = req("GET", "/api/v1/reports", token=token)
    assert code == 200
    print(f"[OK] GET /api/v1/reports -> {len(data)} reports")

    # Groups
    code, data = req("GET", "/api/v1/groups", token=token)
    assert code == 200
    print(f"[OK] GET /api/v1/groups -> {len(data)} groups")

    # Forms
    code, data = req("GET", "/api/v1/forms", token=token)
    assert code == 200
    print(f"[OK] GET /api/v1/forms -> {len(data)} form templates")

    # Chat rooms
    code, data = req("GET", "/api/v1/chat/rooms", token=token)
    assert code == 200
    print(f"[OK] GET /api/v1/chat/rooms -> {len(data)} rooms")

    print("\n=== All checks PASSED! ===")
    print(f"\nBackend:    {BASE}")
    print(f"API Docs:   {BASE}/docs")
    print(f"AdminPanel: http://localhost:3000")
    print(f"Login:      admin / admin123")

if __name__ == "__main__":
    test()
