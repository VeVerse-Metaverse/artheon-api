import unittest

from app.tests_old.base import TestCaseBase
from app.tests_old.client import client


class MainTestCase(unittest.TestCase):
    def test_read_main(self):
        response = client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, "Welcome to VeVerse API! Feel free to check the documentation at /docs.")
