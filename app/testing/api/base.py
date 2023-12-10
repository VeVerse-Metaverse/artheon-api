import unittest
from sqlalchemy.orm import Session
from starlette.testclient import TestClient
from app.database import SessionLocal
from app.main import app


class TestCaseBase(unittest.TestCase):
    db: Session
    key: str
    client = TestClient(app)

    @classmethod
    def setUpClass(cls) -> None:
        cls.db = SessionLocal()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls) -> None:
        super().tearDownClass()
