from io import BytesIO
from typing import Optional

import inject
from PIL import Image

from app.services.math import MathService


class Service:
    maxSide = 8192
    mathService = inject.attr(MathService)

    # noinspection PyMethodMayBeStatic
    def make_preview(self, image: Image, max_size: int = 512):
        original_size = image.size

        target_size = [0, 0]

        if original_size[0] >= original_size[1]:
            target_size[0] = int(max_size)
            target_size[1] = int(original_size[1] / original_size[0] * max_size)
        else:
            target_size[0] = int(original_size[0] / original_size[1] * max_size)
            target_size[1] = int(max_size)

        return image.resize(tuple(target_size), Image.LANCZOS)

    def make_texture(self, image: Image):
        original_size = image.size

        # Get closest power of two size scaled up
        width = self.mathService.next_power_of_two(original_size[0])
        height = self.mathService.next_power_of_two(original_size[1])

        # Find the largest side
        if width > height:
            side = width
        else:
            side = height

        # Limit image size
        if side > self.maxSide:
            side = self.maxSide

        # Square size
        target_size = (side, side)

        return image.resize(target_size, Image.LANCZOS)

    # noinspection PyMethodMayBeStatic
    def to_bytes(self, image: Image, image_format: str, image_quality: Optional[int] = None):
        image_bytes = BytesIO()
        if image_quality:
            image.save(image_bytes, image_format, quality=image_quality)
        else:
            image.save(image_bytes, image_format)
        image_bytes.seek(0)
        return image_bytes
