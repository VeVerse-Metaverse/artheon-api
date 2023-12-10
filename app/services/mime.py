import logging

import magic


class MimeTypeService:
    @classmethod
    def from_buffer(cls, buffer) -> str:
        try:
            return magic.from_buffer(buffer, mime=True)
        except magic.MagicException as e:
            logging.error(e)
            return 'binary/octet-stream'

    @classmethod
    def from_file(cls, file: str) -> str:
        try:
            return magic.from_file(file, mime=True)
        except magic.MagicException as e:
            logging.error(e)
            return 'binary/octet-stream'
