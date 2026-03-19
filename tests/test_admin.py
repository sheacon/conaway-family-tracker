"""Tests for admin routes."""

from unittest.mock import patch

from app import db
from app.models import Config, Family, Person


class TestPeopleList:
    def test_requires_auth(self, client):
        resp = client.get("/admin/")
        assert resp.status_code == 302

    def test_renders(self, auth_client):
        resp = auth_client.get("/admin/")
        assert resp.status_code == 200

    def test_shows_people(self, auth_client, make_person):
        make_person(name="TestPerson")
        resp = auth_client.get("/admin/")
        assert b"TestPerson" in resp.data


class TestNewPerson:
    def test_create_person(self, auth_client):
        resp = auth_client.post("/admin/people/new", data={"name": "NewPerson"})
        assert resp.status_code == 302
        assert Person.query.filter_by(name="NewPerson").first() is not None

    def test_create_person_with_email(self, auth_client):
        auth_client.post("/admin/people/new", data={
            "name": "WithEmail",
            "email": "test@example.com",
        })
        p = Person.query.filter_by(name="WithEmail").first()
        assert p.email == "test@example.com"

    def test_create_person_with_family(self, auth_client, make_family):
        f = make_family(name="Smith")
        auth_client.post("/admin/people/new", data={
            "name": "FamMember",
            "family_id": str(f.id),
        })
        p = Person.query.filter_by(name="FamMember").first()
        assert p.family_id == f.id

    def test_empty_name_rejected(self, auth_client):
        resp = auth_client.post("/admin/people/new", data={"name": ""})
        assert resp.status_code == 302
        # Flashes error and doesn't create
        assert Person.query.filter_by(name="").first() is None

    def test_duplicate_name_rejected(self, auth_client, make_person):
        make_person(name="Existing")
        resp = auth_client.post("/admin/people/new", data={"name": "Existing"})
        assert resp.status_code == 302
        assert Person.query.filter_by(name="Existing").count() == 1


class TestEditPerson:
    def test_get_form(self, auth_client, make_person):
        p = make_person(name="Alice")
        resp = auth_client.get(f"/admin/people/{p.id}/edit")
        assert resp.status_code == 200
        assert b"Alice" in resp.data

    def test_update_all_fields(self, auth_client, make_person, make_family):
        p = make_person(name="Alice")
        f = make_family(name="Smith")
        resp = auth_client.post(f"/admin/people/{p.id}/edit", data={
            "location_label": "Office",
            "latitude": "41.88",
            "longitude": "-87.63",
            "email": "alice@example.com",
            "family_id": str(f.id),
            "notifications": ["trip_created", "trip_started"],
        })
        assert resp.status_code == 302
        db.session.refresh(p)
        assert p.default_location_label == "Office"
        assert p.default_location_lat == 41.88
        assert p.email == "alice@example.com"
        assert p.family_id == f.id
        assert p.get_enabled_notifications() == {"trip_created", "trip_started"}

    def test_clear_email(self, auth_client, make_person):
        p = make_person(name="Bob", email="bob@example.com")
        auth_client.post(f"/admin/people/{p.id}/edit", data={
            "location_label": "Home",
            "latitude": "39.82",
            "longitude": "-98.57",
            "email": "",
        })
        db.session.refresh(p)
        assert p.email is None

    def test_edit_nonexistent_returns_404(self, auth_client):
        resp = auth_client.get("/admin/people/9999/edit")
        assert resp.status_code == 404


class TestFamilyList:
    def test_renders(self, auth_client):
        resp = auth_client.get("/admin/families")
        assert resp.status_code == 200

    def test_shows_families(self, auth_client, make_family):
        make_family(name="TestFamily")
        resp = auth_client.get("/admin/families")
        assert b"TestFamily" in resp.data


class TestNewFamily:
    def test_create_family(self, auth_client):
        resp = auth_client.post("/admin/families/new", data={"name": "NewFamily"})
        assert resp.status_code == 302
        f = Family.query.filter_by(name="NewFamily").first()
        assert f is not None
        assert f.sort_order > 0

    def test_auto_increments_sort_order(self, auth_client, make_family):
        make_family(name="First", sort_order=5)
        auth_client.post("/admin/families/new", data={"name": "Second"})
        f = Family.query.filter_by(name="Second").first()
        assert f.sort_order == 6

    def test_empty_name_rejected(self, auth_client):
        resp = auth_client.post("/admin/families/new", data={"name": ""})
        assert resp.status_code == 302
        assert Family.query.count() == 0

    def test_duplicate_name_rejected(self, auth_client, make_family):
        make_family(name="Existing")
        auth_client.post("/admin/families/new", data={"name": "Existing"})
        assert Family.query.filter_by(name="Existing").count() == 1


class TestEditFamily:
    def test_rename_family(self, auth_client, make_family):
        f = make_family(name="OldName")
        resp = auth_client.post(f"/admin/families/{f.id}/edit", data={"name": "NewName"})
        assert resp.status_code == 302
        db.session.refresh(f)
        assert f.name == "NewName"

    def test_empty_name_rejected(self, auth_client, make_family):
        f = make_family(name="KeepMe")
        auth_client.post(f"/admin/families/{f.id}/edit", data={"name": ""})
        db.session.refresh(f)
        assert f.name == "KeepMe"


class TestDeleteFamily:
    def test_delete_family(self, auth_client, make_family):
        f = make_family(name="ToDelete")
        resp = auth_client.post(f"/admin/families/{f.id}/delete")
        assert resp.status_code == 302
        assert Family.query.get(f.id) is None

    def test_members_unlinked_on_delete(self, auth_client, make_family, make_person):
        f = make_family(name="Smith")
        p = make_person(name="Alice", family=f)
        auth_client.post(f"/admin/families/{f.id}/delete")
        db.session.refresh(p)
        assert p.family_id is None

    def test_delete_nonexistent_returns_404(self, auth_client):
        resp = auth_client.post("/admin/families/9999/delete")
        assert resp.status_code == 404


class TestNotificationsToggle:
    def test_toggle_on(self, auth_client, app):
        auth_client.post("/admin/notifications/toggle")
        row = db.session.get(Config, "notifications_paused")
        assert row.value == "1"

    def test_toggle_off(self, auth_client, app):
        db.session.add(Config(key="notifications_paused", value="1"))
        db.session.commit()
        auth_client.post("/admin/notifications/toggle")
        row = db.session.get(Config, "notifications_paused")
        assert row.value == "0"

    def test_toggle_twice_restores(self, auth_client, app):
        auth_client.post("/admin/notifications/toggle")
        auth_client.post("/admin/notifications/toggle")
        row = db.session.get(Config, "notifications_paused")
        assert row.value == "0"


class TestSendTestEmail:
    def test_sends_email(self, auth_client):
        with patch("app.admin.send_test_notification", return_value=True) as mock:
            resp = auth_client.post("/admin/test-email", data={"email": "a@b.com"})
        assert resp.status_code == 302
        mock.assert_called_once_with("a@b.com")

    def test_empty_email_rejected(self, auth_client):
        resp = auth_client.post("/admin/test-email", data={"email": ""})
        assert resp.status_code == 302

    def test_failure_flashes_error(self, auth_client):
        with patch("app.admin.send_test_notification", return_value=False):
            resp = auth_client.post(
                "/admin/test-email", data={"email": "a@b.com"},
                follow_redirects=True,
            )
        assert b"Failed" in resp.data
