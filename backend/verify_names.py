"""Verify names via API and check encoding."""
import urllib.request
import json

correct = "\u0410\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440"

req = urllib.request.Request(
    "http://localhost:8000/api/v1/auth/login",
    data=json.dumps({"login": "admin", "password": "admin123"}).encode(),
    headers={"Content-Type": "application/json"},
)
token = json.loads(urllib.request.urlopen(req).read())["access_token"]

req2 = urllib.request.Request(
    "http://localhost:8000/api/v1/users/me",
    headers={"Authorization": "Bearer " + token},
)
me = json.loads(urllib.request.urlopen(req2).read())
name = me["full_name"]
name_bytes = len(name.encode("utf-8"))
print(f"API name bytes: {name_bytes}")
print(f"Name unicode codepoints: {[hex(ord(c)) for c in name]}")
print(f"Correct unicode: {[hex(ord(c)) for c in correct]}")
print(f"Match: {name == correct}")
