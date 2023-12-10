import os

import inject
import requests

from app.services.mime import MimeTypeService
from app.tests_old.base import TestCaseBase

audio_url = "https://artheon-objects.s3-eu-west-1.amazonaws.com/0003188412f440c6b96153f8a9b2a209_en-US.wav"
img_preview_url = "https://artheon-objects.s3-eu-west-1.amazonaws.com/0194184f06f94846ba2694f09a99fc44_preview.jpeg"


class MimeTestCase(TestCaseBase):
    mimeTypeService = inject.attr(MimeTypeService)

    def test_image_mime_file(self):
        self.should("get the mime type from a file path")
        mime = self.mimeTypeService.from_file(f"{os.path.dirname(os.path.realpath(__file__))}/../assets/test.jpeg")
        self.assertEqual(mime, "image/jpeg")

    def test_image_mime_buffer(self):
        self.should("get the mime type from a byte buffer")
        file = open(f"{os.path.dirname(os.path.realpath(__file__))}/../assets/test.jpeg", "rb")
        content = file.read(1024)
        mime = self.mimeTypeService.from_buffer(content)
        self.assertEqual(mime, "image/jpeg")
        file.close()

    def test_image_mime_url(self):
        self.should("get the image mime type from a url")
        response = requests.get(img_preview_url)
        content = response.content
        mime = self.mimeTypeService.from_buffer(content)
        self.assertEqual(mime, "image/jpeg")
        response.close()

    def test_audio_mime_url(self):
        self.should("get the audio mime type from a url")
        response = requests.get(audio_url)
        content = response.content
        mime = self.mimeTypeService.from_buffer(content)
        self.assertEqual(mime, "audio/x-wav")
