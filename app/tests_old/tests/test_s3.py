import os

import inject
import requests

from app.services.s3 import S3Service
from app.tests_old.base import TestCaseBase


class S3TestCase(TestCaseBase):
    s3service = inject.attr(S3Service)

    def test_upload(self):
        key = "assets/test.jpeg"
        file = open(f"{os.path.dirname(os.path.realpath(__file__))}/../{key}", "rb")
        file_content = file.read()
        file.seek(0)

        self.should("upload file")
        info = self.s3service.upload(file, self.s3service.bucket, key)
        self.assertIsNotNone(info)
        self.assertIsNotNone(info["url"])
        self.assertIsNotNone(info["mime"])

        self.should("get uploaded file")
        response = requests.get(info["url"])
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIsNotNone(response.content)
        self.assertEqual(file_content, response.content)

        self.should("delete file")
        result = self.s3service.__delete(self.s3service.bucket, key)
        self.assertIsNotNone(result)

        self.should("ensure that file was deleted")
        response = requests.get(info["url"])
        self.assertEqual(response.status_code, 403, response.text)
        file.close()
