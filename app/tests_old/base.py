import inspect
import unittest

from sqlalchemy.orm import Session

from app import models, schemas, crud
from app.database import SessionLocal
from app.tests_old.client import client

test_email = "test@veverse.com"
test_password = "password"


def create_test_user(db: Session, email=test_email, password=test_password) -> models.User:
    user = schemas.UserCreate(email=email, password=password)
    return crud.user.create(db=db, entity=user)


def delete_test_user(db: Session, id: str):
    db.query(models.User).filter(models.User.id == id).delete()
    db.query(models.Entity).filter(models.Entity.id == id).delete()
    db.commit()


def login(email=test_email, password=test_password):
    response = client.post("/login", json=dict(email=email, password=password))
    if response.status_code == 200:
        return True
    return False


def logout():
    client.get("/logout")


class TestCaseBase(unittest.TestCase):
    db: Session
    user: models.User
    logged_in: bool

    @classmethod
    def setUpClass(cls) -> None:
        cls.db = SessionLocal()
        cls.user = create_test_user(cls.db, email=test_email, password=test_password)

    @classmethod
    def tearDownClass(cls) -> None:
        delete_test_user(cls.db, cls.user.id)

    def setUp(self) -> None:
        self.logPoint()

    def tearDown(self) -> None:
        self.logPoint()
        print("\n")

    def logPoint(self):
        calling_function = inspect.stack()[1][3]
        current_test = self.id().split('.')[-1]
        print(f"in {current_test} - {calling_function}()")

    # noinspection PyMethodMayBeStatic
    def should(self, message=None):
        if message is not None and len(message) > 0:
            print(f"should {message}")

    def getCheckedResponsePayload(self, response, payload_key="data"):
        json = response.json()
        data = json[payload_key]
        self.assertIsNotNone(data)
        return data
