from sqlalchemy.orm import Session

from app.tests_old.base import TestCaseBase, login
from app.tests_old.client import client

expected_properties = ["id", "email", "name", "createdAt", "updatedAt", "apiKey", "active", "avatarUrl"]
test_email = "test@veverse.com"
test_password = "password"


class UserTestCase(TestCaseBase):
    db: Session

    @classmethod
    def setUpClass(cls) -> None:
        super(UserTestCase, cls).setUpClass()
        login()

    def test_read_all(self):
        self.should("forbid reading user list")
        response = client.get("/users/")
        self.assertEqual(response.status_code, 405, response.text)

    def test_read_me(self):
        self.should("get my profile information")
        response = client.get("/users/me")
        self.assertEqual(response.status_code, 200, response.text)
        data = self.getCheckedResponsePayload(response)
        self.assertTrue(all(x in data for x in expected_properties))

    def test_read_my_collections(self):
        self.should("get my collections")
        response = client.get("/users/me/collections")
        self.assertEqual(response.status_code, 200, response.text)
        data = self.getCheckedResponsePayload(response)
        self.assertGreaterEqual(len(data), 0)

    def test_read_my_objects(self):
        self.should("get my objects")
        response = client.get("/users/me/objects")
        self.assertEqual(response.status_code, 200, response.text)
        data = self.getCheckedResponsePayload(response)
        self.assertGreaterEqual(len(data), 0)

    def test_update_my_name(self):
        self.should("change my name")
        new_name = "Jason"
        response = client.patch("/users/me", json=dict(name=new_name))
        self.assertEqual(response.status_code, 200, response.text)
        data = self.getCheckedResponsePayload(response)
        self.assertTrue(all(x in data for x in expected_properties))
        self.assertEqual(data["name"], new_name)

    def test_update_my_password(self):
        self.should("change my password")
        new_password = "password"
        response = client.patch("/users/me", json=dict(password=new_password))
        self.assertEqual(response.status_code, 200, response.text)
        data = self.getCheckedResponsePayload(response)
        self.assertTrue(all(x in data for x in expected_properties))

    def test_delete_me(self):
        self.should("not delete user profile")
        response = client.delete("/users/me")
        self.assertEqual(response.status_code, 405, response.text)
