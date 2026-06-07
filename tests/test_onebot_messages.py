"""Tests for converting OneBot message payloads into plain text."""

from qq_group_filter.onebot_message import onebot_message_to_text


def test_string_message_is_returned_unchanged():
    assert onebot_message_to_text("最近有 GPU 租赁吗") == "最近有 GPU 租赁吗"


def test_array_message_concatenates_text_segments():
    message = [
        {"type": "text", "data": {"text": "最近"}},
        {"type": "at", "data": {"qq": "123456"}},
        {"type": "text", "data": {"text": " 有 GPU 租赁吗"}},
    ]

    assert onebot_message_to_text(message) == "最近 有 GPU 租赁吗"


def test_array_message_without_text_returns_empty_string():
    message = [{"type": "image", "data": {"file": "abc.png"}}]

    assert onebot_message_to_text(message) == ""
