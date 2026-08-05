"""CORR-102: Token counter tests."""
from __future__ import annotations

from aegis_phase1.llm.token_counter import TokenCounter


class TestTokenCounterCount:
    def test_count_basic_text(self):
        # "hello world" = 11 chars; 11 // 4 = 2 tokens (minimum 1)
        # Use 12 chars to get 3 tokens
        assert TokenCounter.count("hello world!") == 3

    def test_count_empty_returns_zero(self):
        assert TokenCounter.count("") == 0

    def test_count_none_returns_zero(self):
        assert TokenCounter.count(None) == 0  # type: ignore[arg-type]

    def test_count_short_text_minimum_one(self):
        # 3 chars = 0 // 4 = 0; minimum is 1
        assert TokenCounter.count("abc") == 1

    def test_count_long_text(self):
        # 4000 chars = 1000 tokens
        assert TokenCounter.count("a" * 4000) == 1000

    def test_count_json_payload(self):
        # realistic JSON payload (len 52 chars * 10 = 520 chars; 520/4 = 130)
        payload = '{"sub_domain_id": "D-01.1", "title": "Data at Rest"}' * 10
        assert TokenCounter.count(payload) == 130
        # Sanity: actual len matches our expectation
        assert len(payload) == 520


class TestTokenCounterCountPair:
    def test_count_pair_basic(self):
        sys_t, user_t, total_t = TokenCounter.count_pair("hello world!", "byebye")
        # sys: 12 / 4 = 3, user: 6 / 4 = 1, total = 4
        assert sys_t == 3
        assert user_t == 1
        assert total_t == 4

    def test_count_pair_both_empty(self):
        sys_t, user_t, total_t = TokenCounter.count_pair("", "")
        assert sys_t == 0
        assert user_t == 0
        assert total_t == 0

    def test_count_pair_only_system(self):
        sys_t, user_t, total_t = TokenCounter.count_pair("a" * 400, "")
        assert sys_t == 100
        assert user_t == 0
        assert total_t == 100

    def test_count_pair_only_user(self):
        sys_t, user_t, total_t = TokenCounter.count_pair("", "b" * 400)
        assert sys_t == 0
        assert user_t == 100
        assert total_t == 100
