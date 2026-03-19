"""Tests for authentication routes."""


class TestLogin:
    def test_login_page_renders(self, client):
        resp = client.get("/login")
        assert resp.status_code == 200
        assert b"password" in resp.data.lower()

    def test_login_correct_password(self, client):
        resp = client.post("/login", data={"password": "testpass"})
        assert resp.status_code == 302
        assert "/" in resp.headers["Location"]

    def test_login_wrong_password(self, client):
        resp = client.post("/login", data={"password": "wrong"})
        assert resp.status_code == 200
        assert b"Wrong password" in resp.data

    def test_login_empty_password(self, client):
        resp = client.post("/login", data={"password": ""})
        assert resp.status_code == 200
        assert b"Wrong password" in resp.data

    def test_login_redirects_to_next(self, client):
        resp = client.post(
            "/login?next=/trips",
            data={"password": "testpass"},
        )
        assert resp.status_code == 302
        assert "/trips" in resp.headers["Location"]


class TestLogout:
    def test_logout_redirects(self, auth_client):
        resp = auth_client.get("/logout")
        assert resp.status_code == 302

    def test_logout_clears_session(self, auth_client):
        auth_client.get("/logout")
        resp = auth_client.get("/")
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]


class TestProtectedRoutes:
    def test_dashboard_requires_auth(self, client):
        resp = client.get("/")
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]

    def test_trips_requires_auth(self, client):
        resp = client.get("/trips")
        assert resp.status_code == 302

    def test_admin_requires_auth(self, client):
        resp = client.get("/admin/")
        assert resp.status_code == 302

    def test_new_trip_requires_auth(self, client):
        resp = client.get("/trips/new")
        assert resp.status_code == 302


class TestUserLoader:
    def test_load_valid_user(self, app):
        from app.auth import load_user
        user = load_user("family")
        assert user is not None
        assert user.id == "family"

    def test_load_invalid_user(self, app):
        from app.auth import load_user
        assert load_user("other") is None
        assert load_user("") is None
