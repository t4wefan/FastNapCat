"""Message segment models for [`fastnapcat`](fastnapcat/__init__.py)."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Literal, TypeAlias

import httpx
from PIL import Image
from pydantic import Field

from .base import BaseModel, BaseSegment


class ReceiveTextData(BaseModel):
    text: str = ""


class ReceiveText(BaseSegment[Literal["text"], ReceiveTextData]):
    type: Literal["text"] = "text"
    data: ReceiveTextData = Field(default_factory=ReceiveTextData)


class ReceiveAtData(BaseModel):
    qq: str | int = ""


class ReceiveAt(BaseSegment[Literal["at"], ReceiveAtData]):
    type: Literal["at"] = "at"
    data: ReceiveAtData = Field(default_factory=ReceiveAtData)


class ReceiveImageData(BaseModel):
    file: str | None = None
    url: str | None = None
    sub_type: str | int | None = None
    summary: str | None = None
    file_size: str | int | None = None
    key: str | None = None
    emoji_id: str | None = None
    emoji_package_id: int | None = None


class ReceiveImage(BaseSegment[Literal["image"], ReceiveImageData]):
    type: Literal["image"] = "image"
    data: ReceiveImageData = Field(default_factory=ReceiveImageData)


@dataclass(slots=True)
class ReceiveImageAsset:
    """Convenient wrapper around one received image segment."""

    image: ReceiveImage

    @property
    def file(self) -> str | None:
        return self.image.data.file

    @property
    def url(self) -> str | None:
        return self.image.data.url

    async def download(self, timeout: float = 10.0) -> bytes:
        source = self.url or self.file
        if not source:
            raise ValueError("receive image does not contain a downloadable source")
        if source.startswith("base64://"):
            import base64

            return base64.b64decode(source.removeprefix("base64://"))
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(source)
            response.raise_for_status()
            return response.content

    async def to_pil(self, timeout: float = 10.0) -> Image.Image:
        return Image.open(BytesIO(await self.download(timeout=timeout))).copy()


@dataclass(slots=True)
class ReceiveImages:
    """Typed collection wrapper returned by [`images()`](fastnapcat/di/providers.py:42)."""

    images: list[ReceiveImageAsset]

    def __bool__(self) -> bool:
        return bool(self.images)

    def __len__(self) -> int:
        return len(self.images)

    def __iter__(self):
        return iter(self.images)

    def __getitem__(self, index: int) -> ReceiveImageAsset:
        return self.images[index]

    async def to_pils(self, timeout: float = 10.0) -> list[Image.Image]:
        return [await image.to_pil(timeout=timeout) for image in self.images]


class ReceiveFaceData(BaseModel):
    id: str | int | None = None


class ReceiveFace(BaseSegment[Literal["face"], ReceiveFaceData]):
    type: Literal["face"] = "face"
    data: ReceiveFaceData = Field(default_factory=ReceiveFaceData)


class ReceiveReplyData(BaseModel):
    id: str | int | None = None


class ReceiveReply(BaseSegment[Literal["reply"], ReceiveReplyData]):
    type: Literal["reply"] = "reply"
    data: ReceiveReplyData = Field(default_factory=ReceiveReplyData)


class ReceiveUnknownData(BaseModel):
    pass


class ReceiveUnknown(BaseSegment[str, ReceiveUnknownData | dict[str, object]]):
    type: str
    data: ReceiveUnknownData | dict[str, object] = Field(default_factory=dict)


ReceiveSegment: TypeAlias = (
    ReceiveText | ReceiveAt | ReceiveImage | ReceiveFace | ReceiveReply | ReceiveUnknown
)


class TextSegmentData(BaseModel):
    text: str = ""


class TextSegment(BaseSegment[Literal["text"], TextSegmentData]):
    type: Literal["text"] = "text"
    data: TextSegmentData = Field(default_factory=TextSegmentData)


class AtSegmentData(BaseModel):
    qq: str | int = ""


class AtSegment(BaseSegment[Literal["at"], AtSegmentData]):
    type: Literal["at"] = "at"
    data: AtSegmentData = Field(default_factory=AtSegmentData)


class ReplySegmentData(BaseModel):
    id: str | int = ""


class ReplySegment(BaseSegment[Literal["reply"], ReplySegmentData]):
    type: Literal["reply"] = "reply"
    data: ReplySegmentData = Field(default_factory=ReplySegmentData)


class FaceSegmentData(BaseModel):
    id: str | int = ""


class FaceSegment(BaseSegment[Literal["face"], FaceSegmentData]):
    type: Literal["face"] = "face"
    data: FaceSegmentData = Field(default_factory=FaceSegmentData)


class ImageSegmentData(BaseModel):
    file: str | None = None
    summary: str | None = None
    sub_type: str | None = None


class ImageSegment(BaseSegment[Literal["image"], ImageSegmentData]):
    type: Literal["image"] = "image"
    data: ImageSegmentData = Field(default_factory=ImageSegmentData)


SendMessageSegment: TypeAlias = (
    TextSegment | AtSegment | ReplySegment | FaceSegment | ImageSegment
)
