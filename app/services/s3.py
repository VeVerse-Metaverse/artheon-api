import logging
import os
import urllib
from typing import Optional

import boto3 as boto3
import inject
from boto3.s3.transfer import TransferConfig
from botocore.client import BaseClient
from botocore.exceptions import ClientError

from app import config
from app.services.mime import MimeTypeService

S3_BUCKET = 'veverse'
S3_REGION = 'us-west-1'


class UploadedFile:
    def __init__(self, url: str, mime: str, size: int):
        self.url = url
        self.mime = mime
        self.size = size

    url: str = ''
    mime: str = ''
    size: int = 0


class S3Service:
    bucket = None
    region = S3_REGION
    s3Client: BaseClient = boto3.client('s3')
    mimeTypeService = inject.attr(MimeTypeService)

    def __init__(self):
        if config.settings.env == 'prod':
            self.bucket = f"{S3_BUCKET}-public"
        elif config.settings.env == 'test':
            self.bucket = f"{S3_BUCKET}-test"
        else:
            self.bucket = f"{S3_BUCKET}-dev"

    def __get_root_url(self):
        return f"https://{self.bucket}.s3-{self.region}.amazonaws.com/"

    def __get_key_from_url(self, url: str = None):
        if url is None:
            raise ValueError('url must be a valid url path string')
        return url.replace(self.__get_root_url(), "")

    def get_download_url(self, file_key: str):
        expiration = 3600  # one hour
        try:
            response = self.s3Client.head_object(Bucket=self.bucket, Key=file_key)
            metadata = response['Metadata']
            params = {
                'Bucket': self.bucket,
                'Key': file_key
            }
            if "filename" in metadata:
                params["ResponseContentDisposition"] = urllib.parse.quote('attachment; filename ="' + metadata["filename"] + '"')
            response = self.s3Client.generate_presigned_url('get_object', Params=params, ExpiresIn=expiration)
        except ClientError as e:
            logging.error(e)
            return None
        return response

    def upload(self, file, bucket: str = bucket, key: str = None, extra_args=None, callback=None,
               config: TransferConfig = None) -> Optional[UploadedFile]:
        """Uploads the file to S3 bucket, determines the MimeType automatically, but it can be overridden with extra_args={ContentType: ...}"""
        if key is None:
            raise ValueError('key must be a valid url path string')

        mime_type = self.mimeTypeService.from_buffer(file.read(1024))
        file.seek(0, os.SEEK_END)
        size = file.tell()
        file.seek(0)

        default_args = dict(ContentType=mime_type)

        if extra_args is None:
            extra_args = default_args
        else:
            extra_args = {**default_args, **extra_args}

        try:
            self.s3Client.upload_fileobj(file, bucket, key, ExtraArgs=extra_args, Callback=callback, Config=config)
            return UploadedFile(url=f"https://{self.bucket}.s3-{self.region}.amazonaws.com/{key}", mime=mime_type, size=size)
        except ClientError as e:
            logging.error(e)
            return None

    def delete_file_by_url(self, url: str):
        key = self.__get_key_from_url(url)
        self.__delete(bucket=self.bucket, key=key)

    def __delete(self, bucket: str, key: str):
        try:
            return self.s3Client.delete_object(Bucket=bucket, Key=key)
        except ClientError as e:
            logging.error(e)
            return None
