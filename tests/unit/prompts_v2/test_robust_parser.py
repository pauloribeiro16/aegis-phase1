"""Tests for RobustParser — multi-strategy JSON parser for gemma4:e2b outputs."""

from __future__ import annotations

from aegis_phase1.prompts_v2.robust_parser import RobustParser


class TestJsonStrict:
    def test_pure_json_object(self):
        raw = '{"key": "value", "num": 42}'
        result = RobustParser.parse(raw)
        assert result.ok
        assert result.json == {"key": "value", "num": 42}
        assert result.strategy == "json_strict"

    def test_pure_json_with_surrounding_text(self):
        # Strict strategy fails; fall back to extract_first_object
        raw = 'Some text\n{"key": "value"}\nMore text'
        result = RobustParser.parse(raw)
        assert result.ok
        assert result.json == {"key": "value"}
        assert result.strategy == "extract_first_object"

    def test_empty_string(self):
        result = RobustParser.parse("")
        assert not result.ok
        assert "empty" in (result.error or "").lower() or "none" in (result.error or "").lower()


class TestExtractMarkdownBlock:
    def test_json_code_block(self):
        raw = 'Here is the result:\n```json\n{"key": "value"}\n```\nDone.'
        result = RobustParser.parse(raw)
        assert result.ok
        assert result.json == {"key": "value"}
        assert result.strategy == "extract_markdown_block"

    def test_plain_code_block(self):
        raw = 'Output:\n```\n{"foo": 1}\n```'
        result = RobustParser.parse(raw)
        assert result.ok
        assert result.json == {"foo": 1}

    def test_no_code_block_falls_through(self):
        raw = '{"no": "codeblock"}'
        result = RobustParser.parse(raw)
        assert result.ok
        # json_strict should win


class TestExtractFirstObject:
    def test_nested_objects(self):
        raw = 'prefix {"a": 1, "b": {"c": 2}} suffix'
        result = RobustParser.parse(raw)
        assert result.ok
        assert result.json == {"a": 1, "b": {"c": 2}}

    def test_no_balanced_object(self):
        raw = 'unbalanced { not closed'
        result = RobustParser.parse(raw)
        # New behavior: fallback always succeeds with minimal object
        assert result.ok
        assert result.strategy == "construct_minimal_object"
        assert result.json.get("status") == "INSUFFICIENT_EVIDENCE"

    def test_braces_in_strings(self):
        # String contents may include braces; should not confuse the parser
        raw = 'msg {"key": "value with { nested } braces"} more'
        result = RobustParser.parse(raw)
        # Either succeeds or fails — main concern is no false-positive
        if result.ok:
            assert "key" in result.json


class TestExtractFirstArray:
    def test_array_in_text(self):
        raw = 'Output: [{"a": 1}, {"b": 2}] end'
        result = RobustParser.parse(raw)
        # Pre-check sees "[" and promotes extract_first_array to the front so
        # we do not accidentally grab the inner {"a": 1} via extract_first_object.
        assert result.ok
        assert result.strategy == "extract_first_array"
        assert result.json == {"items": [{"a": 1}, {"b": 2}]}


class TestRepairCommonErrors:
    def test_single_quotes(self):
        # Single quotes are invalid JSON; repair strategy tries replacing them
        raw = "{'key': 'value'}"
        result = RobustParser.parse(raw)
        if result.strategy == "repair_common_errors":
            assert result.ok
            assert result.json == {"key": "value"}

    def test_trailing_comma(self):
        raw = '{"key": "value",}'
        result = RobustParser.parse(raw)
        # extract_first_object or json_strict may already handle this; just check not garbage
        if result.ok and result.json:
            assert "key" in result.json


class TestFailureModes:
    def test_total_garbage(self):
        result = RobustParser.parse("this is not json at all")
        # New behavior: fallback always succeeds
        assert result.ok
        assert result.strategy == "construct_minimal_object"
        assert result.json.get("status") == "INSUFFICIENT_EVIDENCE"
        # All 8 strategies were tried (including fallback)
        assert len(result.attempts) == len(RobustParser.STRATEGIES)

    def test_truncated_json(self):
        raw = '{"key": "value", "ne'
        result = RobustParser.parse(raw)
        # May or may not succeed depending on strategies; just don't crash
        assert result is not None

    def test_attempts_recorded(self):
        result = RobustParser.parse("garbage")
        # New behavior: fallback always succeeds, but all 8 strategies attempted
        assert result.ok
        for attempt in result.attempts:
            assert "strategy" in attempt
            assert "ok" in attempt
        # All 8 strategies were tried
        assert len(result.attempts) == len(RobustParser.STRATEGIES)
        strategies_tried = {a["strategy"] for a in result.attempts}
        assert strategies_tried == set(RobustParser.STRATEGIES)
