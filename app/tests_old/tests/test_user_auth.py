from sqlalchemy.orm import Session

from app import models
from app.constants import COOKIE_DOMAIN, COOKIE_NAME
from app.tests_old.base import TestCaseBase, delete_test_user
from app.tests_old.client import client

expected_properties = ["id", "email", "name", "createdAt", "updatedAt", "apiKey", "active", "avatarUrl"]
email = "test@veverse.com"
password = "password"


class UserAuthTestCase(TestCaseBase):
    db: Session
    user: models.User

    def test_register_existing(self):
        self.should("forbid registering existing user")
        response = client.post("/users/", json=dict(email=self.user.email, password=password))
        self.assertEqual(response.status_code, 400, response.text)

    def test_register_new(self):
        self.should("allow registering existing user")
        response = client.post("/users/", json=dict(email=f"new@veverse.com", password=password))
        self.assertEqual(response.status_code, 200, response.text)
        data = self.getCheckedResponsePayload(response)
        self.assertTrue(all(x in data for x in expected_properties))
        delete_test_user(self.db, data["id"])

    def test_login_incorrect(self):
        self.should("fail with incorrect user email and password")
        response = client.post("/login", json=dict(email=email, password='incorrect-password'))
        self.assertEqual(response.status_code, 403, response.text)

    def test_login(self):
        self.should("login user and get cookie")
        response = client.post("/login", json=dict(email=email, password=password))
        self.assertEqual(response.status_code, 200, response.text)
        data = self.getCheckedResponsePayload(response)
        key_cookie = response.cookies[COOKIE_NAME]
        self.assertIsNotNone(key_cookie)
        self.assertTrue(all(x in data for x in expected_properties))

    def test_logout(self):
        self.should("log out and clear the cookie")
        response = client.post("/login", json=dict(email=email, password=password))
        self.assertEqual(response.status_code, 200, response.text)
        response = client.get("/logout")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIsNone(response.cookies.get(COOKIE_NAME, domain=COOKIE_DOMAIN))
