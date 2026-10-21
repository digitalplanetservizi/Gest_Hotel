"""Read-only smoke check of the live stack, including session and CSRF handling.

Reads local .env without printing secrets. Run after scripts/start.ps1.
Does not create or modify hotel business data.
"""

import http.cookiejar
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener

ROOT = Path(__file__).resolve().parent.parent


def local_environment():
    values = dict(os.environ)
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8-sig").splitlines():
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values.setdefault(key, value)
    return values


def main():
    config = local_environment()
    base = os.getenv("HOTEL_TEST_URL", f"http://127.0.0.1:{config.get('HTTP_PORT', '18080')}")
    cookies = http.cookiejar.CookieJar()
    client = build_opener(HTTPCookieProcessor(cookies))

    def fetch(path, data=None, csrf=True):
        headers = {"Accept": "application/json", "Origin": base}
        if csrf:
            token = next((c.value for c in cookies if c.name == "csrftoken"), "")
            if token:
                headers["X-CSRFToken"] = token
        payload = None
        if data is not None:
            payload = json.dumps(data).encode()
            headers["Content-Type"] = "application/json"
        return client.open(Request(base + path, data=payload, headers=headers), timeout=15)

    def expect_error(path, expected, data=None, csrf=True):
        try:
            fetch(path, data, csrf)
        except HTTPError as error:
            assert error.code == expected, f"{path}: expected {expected}, got {error.code}"
        else:
            raise AssertionError(f"{path}: expected HTTP {expected}")

    with fetch("/healthz") as response:
        assert response.status == 200
    with fetch("/api/v1/health/") as response:
        assert response.status == 200
        assert response.headers["Cache-Control"] == "no-store"
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["Content-Security-Policy"]
    for path in ("/", "/planning", "/settings"):
        with fetch(path) as response:
            html = response.read().decode()
            assert "<app-root" in html, f"SPA fallback failed at {path}"
    expect_error("/api/v1/auth/me/", 401)
    with fetch("/api/v1/auth/csrf/") as response:
        assert response.status == 200
    login = {"email": config["BOOTSTRAP_ADMIN_EMAIL"], "password": config["BOOTSTRAP_ADMIN_PASSWORD"]}
    expect_error("/api/v1/auth/login/", 403, login, csrf=False)
    with fetch("/api/v1/auth/login/", login) as response:
        assert response.status == 200
    session = next(c for c in cookies if c.name == "sessionid")
    assert session.has_nonstandard_attr("HttpOnly")
    for path in (
        "auth/me/", "settings/", "rooms/", "groups/", "rates/", "price-items/",
        "stays/", "cash/reasons/", "cash/shifts/", "cash/movements/",
        "inventory/items/", "inventory/movements/", "reports/", "users/", "dashboard/",
        "planning/?start=2026-10-19&end=2026-10-26",
    ):
        with fetch("/api/v1/" + path) as response:
            assert response.status == 200, path
            json.loads(response.read())
    expect_error("/api/v1/auth/logout/", 403, {}, csrf=False)
    with fetch("/api/v1/auth/logout/", {}) as response:
        assert response.status in (200, 204)
    expect_error("/api/v1/auth/me/", 401)
    print("Live smoke check passed: routing, API resources, authentication, CSRF, headers and logout.")


if __name__ == "__main__":
    main()
