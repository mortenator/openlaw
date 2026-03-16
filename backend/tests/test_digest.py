"""Tests for digest.py — sort logic, HTML builder, and early-exit guards."""
import pytest
from app.services.digest import _get_join, _sort_key, _build_html, _build_text


# ── _get_join ──────────────────────────────────────────────────────────────

def test_get_join_dict():
    row = {"contacts": {"name": "Alice", "health_score": 40}}
    assert _get_join(row, "contacts") == {"name": "Alice", "health_score": 40}


def test_get_join_list_with_item():
    row = {"contacts": [{"name": "Bob", "health_score": 20}]}
    assert _get_join(row, "contacts")["name"] == "Bob"


def test_get_join_empty_list():
    """Must not raise IndexError on empty join."""
    row = {"contacts": []}
    assert _get_join(row, "contacts") == {}


def test_get_join_none():
    row = {}
    assert _get_join(row, "contacts") == {}


# ── _sort_key ──────────────────────────────────────────────────────────────

def _make_row(health, created_at="2026-01-01T00:00:00Z"):
    return {
        "contacts": {"health_score": health},
        "signals": {"created_at": created_at},
    }


def test_sort_worst_health_first():
    rows = [_make_row(80), _make_row(20), _make_row(50)]
    rows.sort(key=_sort_key)
    assert [_get_join(r, "contacts")["health_score"] for r in rows] == [20, 50, 80]


def test_sort_none_health_before_zero():
    """Unknown health (-1 sentinel) sorts before 0."""
    rows = [_make_row(0), {"contacts": {}, "signals": {}}]
    rows.sort(key=_sort_key)
    # unknown contact (no health_score) should be first
    assert _get_join(rows[0], "contacts").get("health_score") is None


def test_sort_recent_signal_first_when_same_health():
    rows = [
        _make_row(30, "2026-01-01T00:00:00Z"),
        _make_row(30, "2026-03-01T00:00:00Z"),
    ]
    rows.sort(key=_sort_key)
    assert _get_join(rows[0], "signals")["created_at"] == "2026-03-01T00:00:00Z"


# ── _build_html ────────────────────────────────────────────────────────────

def _make_suggestion(name="Alice", role="Partner", body="Hi Alice", trigger="90 days"):
    return {
        "contacts": {"name": name, "role": role},
        "signals": {"headline": "Some news"},
        "body": body,
        "trigger_summary": trigger,
    }


def test_build_html_contains_name():
    html = _build_html([_make_suggestion(name="Alice")], "March 15, 2026")
    assert "Alice" in html


def test_build_html_escapes_xss():
    html = _build_html([_make_suggestion(name="<script>alert(1)</script>")], "March 15, 2026")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_build_html_newlines_to_br():
    html = _build_html([_make_suggestion(body="Line 1\nLine 2")], "March 15, 2026")
    assert "<br>" in html


def test_build_html_empty_join_no_crash():
    """Orphaned suggestion (no contact join) must not crash."""
    suggestion = {"contacts": [], "signals": [], "body": "Hi", "trigger_summary": None}
    html = _build_html([suggestion], "March 15, 2026")
    assert "Unknown" in html  # fallback name


# ── _build_text ────────────────────────────────────────────────────────────

def test_build_text_contains_name():
    text = _build_text([_make_suggestion(name="Bob")], "March 15, 2026")
    assert "Bob" in text


def test_build_text_numbered():
    text = _build_text([_make_suggestion(), _make_suggestion(name="Carol")], "March 15, 2026")
    assert "1." in text
    assert "2." in text
