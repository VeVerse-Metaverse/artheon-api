import io

import inject

from app.services import s3
from app.services.s3 import S3Service


class Service:
    s3Service = inject.attr(S3Service)

    def upload_file(self, file_key: str, file_bytes: bytearray, extra_args: dict = None) -> s3.UploadedFile:
        r"""Uploads file to the S3 storage"""
        file_bytes = io.BytesIO(file_bytes)
        return self.s3Service.upload(file_bytes, bucket=self.s3Service.bucket, key=file_key, extra_args=extra_args)

    def delete_file(self, url: str):
        r"""Deletes file from the S3 storage using its URL"""
        self.s3Service.delete_file_by_url(url)
