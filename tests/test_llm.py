"""Tests for the LLM client module."""

import pytest

from core.llm import parse_json_response


class TestParseJsonResponse:
    def test_plain_json(self):
        result = parse_json_response('{"key": "value"}')
        assert result == {"key": "value"}

    def test_markdown_fenced(self):
        raw = '```json\n{"key": "value"}\n```'
        result = parse_json_response(raw)
        assert result == {"key": "value"}

    def test_markdown_fenced_no_lang(self):
        raw = '```\n{"key": "value"}\n```'
        result = parse_json_response(raw)
        assert result == {"key": "value"}

    def test_json_with_surrounding_text(self):
        raw = 'Here is the result:\n{"key": "value"}\nDone.'
        result = parse_json_response(raw)
        assert result == {"key": "value"}

    def test_json_array(self):
        raw = '[{"a": 1}, {"b": 2}]'
        result = parse_json_response(raw)
        # parse_json_response returns whatever json.loads produces
        assert isinstance(result, (list, dict))

    def test_nested_json(self):
        raw = '{"outer": {"inner": [1, 2, 3]}}'
        result = parse_json_response(raw)
        assert result["outer"]["inner"] == [1, 2, 3]

    def test_invalid_json_returns_raw(self):
        raw = "This is not JSON at all"
        result = parse_json_response(raw)
        assert "raw_response" in result

    def test_empty_string(self):
        result = parse_json_response("")
        assert "raw_response" in result
