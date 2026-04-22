"""Message segment builder for [`fastnapcat`](fastnapcat/__init__.py)."""

from __future__ import annotations

from fastnapcat.models.segments import (
    AtSegment,
    AtSegmentData,
    FaceSegment,
    FaceSegmentData,
    ImageSegment,
    ImageSegmentData,
    ReplySegment,
    ReplySegmentData,
    SendMessageSegment,
    TextSegment,
    TextSegmentData,
)


class MessageBuilder:
    @staticmethod
    def text(content: str) -> TextSegment:
        return TextSegment(type="text", data=TextSegmentData(text=content))

    @staticmethod
    def at(user_id: int) -> AtSegment:
        return AtSegment(type="at", data=AtSegmentData(qq=str(user_id)))

    @staticmethod
    def face(face_id: int) -> FaceSegment:
        return FaceSegment(type="face", data=FaceSegmentData(id=str(face_id)))

    @staticmethod
    def image(
        file: str, summary: str | None = None, sub_type: str | None = None
    ) -> ImageSegment:
        return ImageSegment(
            type="image",
            data=ImageSegmentData(file=file, summary=summary, sub_type=sub_type),
        )

    @staticmethod
    def reply(message_id: int) -> ReplySegment:
        return ReplySegment(type="reply", data=ReplySegmentData(id=str(message_id)))

    @staticmethod
    def chain(*segments: SendMessageSegment) -> list[SendMessageSegment]:
        return list(segments)


message_builder = MessageBuilder()
