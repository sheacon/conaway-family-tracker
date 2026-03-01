from app import db
from app.models import Config, Person, Family


class TestPeopleAdmin:
    def test_people_list_renders(self, auth_client):
        resp = auth_client.get("/admin/")
        assert resp.status_code == 200

    def test_create_person(self, auth_client, make_family):
        fam = make_family(name="Clan")
        resp = auth_client.post("/admin/people/new", data={
            "name": "NewPerson",
            "email": "new@example.com",
            "family_id": str(fam.id),
        }, follow_redirects=True)
        assert b"Added NewPerson" in resp.data
        p = Person.query.filter_by(name="NewPerson").first()
        assert p is not None
        assert p.email == "new@example.com"
        assert p.family_id == fam.id

    def test_create_person_empty_name(self, auth_client):
        resp = auth_client.post("/admin/people/new", data={
            "name": "",
        }, follow_redirects=True)
        assert b"Name is required" in resp.data

    def test_create_person_duplicate_name(self, auth_client, make_person):
        make_person(name="Existing")
        resp = auth_client.post("/admin/people/new", data={
            "name": "Existing",
        }, follow_redirects=True)
        assert b"already exists" in resp.data

    def test_create_person_redirects_to_edit(self, auth_client):
        resp = auth_client.post("/admin/people/new", data={
            "name": "RedirectMe",
        })
        assert resp.status_code == 302
        p = Person.query.filter_by(name="RedirectMe").first()
        assert f"/admin/people/{p.id}/edit" in resp.headers["Location"]

    def test_edit_person_renders(self, auth_client, make_person):
        p = make_person(name="Editable")
        resp = auth_client.get(f"/admin/people/{p.id}/edit")
        assert resp.status_code == 200
        assert b"Editable" in resp.data

    def test_edit_person_updates(self, auth_client, make_person, make_family):
        fam = make_family(name="NewFam")
        p = make_person(name="ToEdit")
        resp = auth_client.post(f"/admin/people/{p.id}/edit", data={
            "location_label": "Office",
            "latitude": "40.7128",
            "longitude": "-74.006",
            "email": "edited@example.com",
            "color": "#ff0000",
            "family_id": str(fam.id),
        }, follow_redirects=True)
        assert b"Updated ToEdit" in resp.data
        db.session.refresh(p)
        assert p.default_location_label == "Office"
        assert p.email == "edited@example.com"
        assert p.color == "#ff0000"
        assert p.family_id == fam.id

    def test_edit_person_404(self, auth_client):
        resp = auth_client.get("/admin/people/9999/edit")
        assert resp.status_code == 404


class TestFamilyAdmin:
    def test_family_list_renders(self, auth_client):
        resp = auth_client.get("/admin/families")
        assert resp.status_code == 200

    def test_create_family(self, auth_client):
        resp = auth_client.post("/admin/families/new", data={
            "name": "NewFamily",
        }, follow_redirects=True)
        assert b"Created family" in resp.data
        assert Family.query.filter_by(name="NewFamily").first() is not None

    def test_create_family_auto_sort_order(self, auth_client, make_family):
        make_family(name="First", sort_order=5)
        auth_client.post("/admin/families/new", data={"name": "Second"})
        second = Family.query.filter_by(name="Second").first()
        assert second.sort_order == 6

    def test_create_family_empty_name(self, auth_client):
        resp = auth_client.post("/admin/families/new", data={
            "name": "",
        }, follow_redirects=True)
        assert b"Family name is required" in resp.data

    def test_create_family_duplicate_name(self, auth_client, make_family):
        make_family(name="Duped")
        resp = auth_client.post("/admin/families/new", data={
            "name": "Duped",
        }, follow_redirects=True)
        assert b"already exists" in resp.data

    def test_edit_family_renames(self, auth_client, make_family):
        fam = make_family(name="OldName")
        resp = auth_client.post(f"/admin/families/{fam.id}/edit", data={
            "name": "Renamed",
        }, follow_redirects=True)
        assert b"Renamed family" in resp.data
        db.session.refresh(fam)
        assert fam.name == "Renamed"

    def test_edit_family_empty_name(self, auth_client, make_family):
        fam = make_family(name="KeepMe")
        resp = auth_client.post(f"/admin/families/{fam.id}/edit", data={
            "name": "",
        }, follow_redirects=True)
        assert b"Family name is required" in resp.data

    def test_edit_family_404(self, auth_client):
        resp = auth_client.post("/admin/families/9999/edit", data={"name": "Ghost"})
        assert resp.status_code == 404

    def test_delete_family_orphans_members(self, auth_client, make_family, make_person):
        fam = make_family(name="Doomed")
        p = make_person(name="Child", family=fam)
        auth_client.post(f"/admin/families/{fam.id}/delete")
        db.session.refresh(p)
        assert p.family_id is None
        assert db.session.get(Family, fam.id) is None

    def test_delete_family_flash(self, auth_client, make_family):
        fam = make_family(name="ByeBye")
        resp = auth_client.post(f"/admin/families/{fam.id}/delete",
                                follow_redirects=True)
        assert b"Deleted family" in resp.data

    def test_delete_family_404(self, auth_client):
        resp = auth_client.post("/admin/families/9999/delete")
        assert resp.status_code == 404


class TestNotificationsToggle:
    def test_toggle_pauses(self, auth_client, app):
        auth_client.post("/admin/notifications/toggle")
        with app.app_context():
            row = db.session.get(Config, "notifications_paused")
            assert row.value == "1"

    def test_toggle_resumes(self, auth_client, app):
        with app.app_context():
            db.session.add(Config(key="notifications_paused", value="1"))
            db.session.commit()
        auth_client.post("/admin/notifications/toggle")
        with app.app_context():
            row = db.session.get(Config, "notifications_paused")
            assert row.value == "0"

    def test_page_shows_paused_state(self, auth_client, app):
        with app.app_context():
            db.session.add(Config(key="notifications_paused", value="1"))
            db.session.commit()
        resp = auth_client.get("/admin/")
        assert b"notifications are paused" in resp.data.lower()
        assert b"Resume Notifications" in resp.data

    def test_page_shows_active_state(self, auth_client):
        resp = auth_client.get("/admin/")
        assert b"Pause Notifications" in resp.data

    def test_requires_login(self, client):
        resp = client.post("/admin/notifications/toggle")
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]
