"""
tests/test_scrape.py — Unit tests for scrape.py (Phase 1B).

No real network connections.  All HTTP is mocked via unittest.mock.
DB tests use a temporary SQLite file so they are isolated from the
in-memory engine shared by test_db.py.

Run with:
    pytest tests/test_scrape.py -v
"""
from __future__ import annotations

import asyncio
import hashlib
import os
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
import requests

import scrape
from scrape import (
    MAX_DOWNLOAD_BYTES,
    MAX_EXTRACTED_TEXT_CHARS,
    MAX_RETURN_CHARS,
    _build_proxy_url,
    _extract_text,
    _fetch_one,
    _is_onion,
    get_tor_session,
    scrape_multiple,
    scrape_single,
)
from config import TOR_PROXY_HOST, TOR_PROXY_PORT

# ---------------------------------------------------------------------------
# Separate SQLite DB so these tests never touch test_db.py's in-memory engine
# ---------------------------------------------------------------------------

_SCRAPE_DB_FILE = "scrape_test_temp.db"
SCRAPE_TEST_DB_URL = f"sqlite:///{_SCRAPE_DB_FILE}"


def _run_scrape_multiple(urls_data, max_workers: int = 5):
    """Run async scrape_multiple from synchronous tests."""
    return asyncio.run(scrape_multiple(urls_data, max_workers))


def _run_scrape_single(url_data):
    return asyncio.run(scrape_single(url_data))


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

def make_mock_response(
    status: int = 200,
    body: bytes = b"<html><body>hello world</body></html>",
    content_type: str = "text/html",
) -> MagicMock:
    """
    Build a MagicMock that behaves like an aiohttp response.

    Supports:
        async with session.get(url) as resp:      (resp is the mock itself)
        async for chunk in resp.content.iter_chunked(n):
    """
    resp = MagicMock()
    resp.status = status
    resp.headers = {"Content-Type": content_type}
    resp.charset = "utf-8"

    async def iter_chunked(n: int):
        yield body

    resp.content.iter_chunked = iter_chunked
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=False)
    return resp


def make_session_mock(responses) -> MagicMock:
    """
    Return an aiohttp.ClientSession mock whose .get() yields the given
    response(s).  Pass a single mock for uniform behaviour, or a list for
    side_effect (one response consumed per call).
    """
    session = MagicMock()
    if isinstance(responses, list):
        session.get = MagicMock(side_effect=responses)
    else:
        session.get = MagicMock(return_value=responses)
    return session


def run_fetch(session, url_data, semaphore_size: int = 1):
    """Run _fetch_one synchronously in a fresh event loop."""
    async def _inner():
        sem = asyncio.Semaphore(semaphore_size)
        return await _fetch_one(session, url_data, sem)
    return asyncio.run(_inner())


# ---------------------------------------------------------------------------
# DB fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def _scrape_db_engine():
    """
    Module-scoped SQLite engine for DB persistence tests.

    Uses a file-based DB (not :memory:) so it is fully isolated from the
    in-memory engine used by test_db.py's module-scoped _db_engine fixture.
    """
    from db.models import Base
    from db.session import _engine_cache, get_engine

    engine = get_engine(SCRAPE_TEST_DB_URL)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()
    _engine_cache.pop(SCRAPE_TEST_DB_URL, None)
    if os.path.exists(_SCRAPE_DB_FILE):
        os.remove(_SCRAPE_DB_FILE)


@pytest.fixture
def _clean_db(_scrape_db_engine):
    """Wipe pages + sources before and after each DB test."""
    from sqlalchemy.orm import sessionmaker
    from db.models import Page, Source

    SM = sessionmaker(bind=_scrape_db_engine)

    def _wipe():
        s = SM()
        s.query(Page).delete()   # delete child rows first (FK)
        s.query(Source).delete()
        s.commit()
        s.close()

    _wipe()
    yield
    _wipe()


@pytest.fixture
def _db_url(monkeypatch, _clean_db):
    """
    Redirect DATABASE_URL in both config and db.session to the test SQLite
    file so that scrape_multiple → _persist_pages writes there.
    """
    monkeypatch.setattr("config.DATABASE_URL", SCRAPE_TEST_DB_URL)
    monkeypatch.setattr("db.session.DATABASE_URL", SCRAPE_TEST_DB_URL)


# ---------------------------------------------------------------------------
# TestPublicAPISignatures
# ---------------------------------------------------------------------------

class TestPublicAPISignatures:
    def test_scrape_multiple_returns_dict(self):
        url = "http://example.com/page"
        with patch("scrape._gather_all", new=AsyncMock(return_value=[
            (url, "Example - hello world", b"data", "hello world", None),
        ])):
            result = _run_scrape_multiple([{"link": url, "title": "Example"}])

        assert isinstance(result, dict)
        assert all(isinstance(k, str) for k in result)
        assert all(isinstance(v, str) for v in result.values())

    def test_scrape_single_returns_tuple(self):
        url = "http://example.com/page"
        with patch("scrape._gather_all", new=AsyncMock(return_value=[
            (url, "Example - hello world", b"data", "hello world", None),
        ])):
            result = _run_scrape_single({"link": url, "title": "Example"})

        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_get_tor_session_returns_requests_session(self):
        result = get_tor_session()
        assert isinstance(result, requests.Session)
        assert "http" in result.proxies
        assert "https" in result.proxies


# ---------------------------------------------------------------------------
# TestContentExtraction
# ---------------------------------------------------------------------------

class TestContentExtraction:
    def test_trafilatura_used_first(self):
        with patch("scrape.trafilatura.extract", return_value="extracted text"), \
             patch("scrape.BeautifulSoup") as mock_bs:
            result = _extract_text("<html><body>hello</body></html>")

        assert result == "extracted text"
        mock_bs.assert_not_called()

    def test_beautifulsoup_fallback_when_trafilatura_none(self):
        with patch("scrape.trafilatura.extract", return_value=None):
            result = _extract_text("<html><body>fallback content</body></html>")

        assert len(result) > 0

    def test_beautifulsoup_fallback_when_trafilatura_empty(self):
        with patch("scrape.trafilatura.extract", return_value=""):
            result = _extract_text("<html><body>fallback content</body></html>")

        assert len(result) > 0

    def test_trafilatura_exception_falls_back(self):
        with patch("scrape.trafilatura.extract", side_effect=Exception("lxml error")):
            result = _extract_text("<html><body>fallback content</body></html>")

        assert len(result) > 0

    def test_truncates_to_max_extracted_chars(self):
        huge = f"<html><body>{'x' * (MAX_EXTRACTED_TEXT_CHARS + 5000)}</body></html>"
        with patch("scrape.trafilatura.extract", return_value=None):
            result = _extract_text(huge)

        assert len(result) <= MAX_EXTRACTED_TEXT_CHARS


# ---------------------------------------------------------------------------
# TestRetryLogic
# ---------------------------------------------------------------------------

class TestRetryLogic:
    """
    Tests call _fetch_one directly.  RETRY_DELAYS is patched to (0, 0, 0) so
    asyncio.sleep(0) is called instead of the real 2 s / 4 s / 8 s delays.
    """

    def _run(self, session, url_data):
        with patch.object(scrape, "RETRY_DELAYS", (0.0, 0.0, 0.0)):
            return run_fetch(session, url_data)

    def test_503_twice_then_200_returns_content(self):
        url_data = {"link": "http://example.com/", "title": "T"}
        session = make_session_mock([
            make_mock_response(status=503),
            make_mock_response(status=503),
            make_mock_response(status=200, body=b"<html><body>success</body></html>"),
        ])

        url, display_text, raw_bytes, db_text, _posted_at = self._run(session, url_data)

        assert url == "http://example.com/"
        assert raw_bytes is not None
        assert session.get.call_count == 3

    def test_all_4_attempts_fail_returns_title(self):
        url_data = {"link": "http://example.com/", "title": "MyTitle"}
        session = make_session_mock([make_mock_response(status=503)] * 4)

        url, display_text, raw_bytes, db_text, _posted_at = self._run(session, url_data)

        assert url == "http://example.com/"
        assert raw_bytes is None
        assert db_text is None
        assert display_text == "MyTitle"
        assert session.get.call_count == 4

    def test_client_error_retried(self):
        url_data = {"link": "http://example.com/", "title": "T"}
        ok_resp = make_mock_response(status=200, body=b"<html><body>ok</body></html>")
        session = MagicMock()
        session.get = MagicMock(side_effect=[
            aiohttp.ClientConnectionError("conn error"),
            aiohttp.ClientConnectionError("conn error"),
            ok_resp,
        ])

        url, display_text, raw_bytes, db_text, _posted_at = self._run(session, url_data)

        assert raw_bytes is not None
        assert session.get.call_count == 3

    def test_timeout_retried(self):
        url_data = {"link": "http://example.com/", "title": "T"}
        ok_resp = make_mock_response(status=200, body=b"<html><body>ok</body></html>")
        session = MagicMock()
        session.get = MagicMock(side_effect=[
            asyncio.TimeoutError(),
            asyncio.TimeoutError(),
            ok_resp,
        ])

        url, display_text, raw_bytes, db_text, _posted_at = self._run(session, url_data)

        assert raw_bytes is not None
        assert session.get.call_count == 3

    def test_404_no_retry(self):
        url_data = {"link": "http://example.com/missing", "title": "T"}
        session = make_session_mock(make_mock_response(status=404))

        url, display_text, raw_bytes, db_text, _posted_at = self._run(session, url_data)

        assert raw_bytes is None
        assert session.get.call_count == 1

    def test_ssrf_blocks_loopback_without_http_get(self):
        """Internal IPs must not reach aiohttp session.get (SSRF prevention)."""
        url_data = {"link": "http://127.0.0.1:5432/", "title": "T"}
        session = MagicMock()
        session.get = MagicMock()
        url, display_text, raw_bytes, db_text, posted_at = self._run(session, url_data)
        assert raw_bytes is None
        assert db_text is None
        assert posted_at is None
        session.get.assert_not_called()


# ---------------------------------------------------------------------------
# TestDeduplication
# ---------------------------------------------------------------------------

class TestDeduplication:
    def test_same_url_deduplicated(self):
        """Identical URL appearing twice in the input is fetched only once."""
        urls = [
            {"link": "http://example.com/", "title": "A"},
            {"link": "http://example.com/", "title": "B"},
        ]
        captured: list = []

        async def fake_gather(unique_urls_data, max_workers):
            captured.extend(unique_urls_data)
            return [("http://example.com/", "A - text", b"data", "text", None)]

        with patch("scrape._gather_all", side_effect=fake_gather):
            _run_scrape_multiple(urls)

        assert len(captured) == 1
        assert captured[0]["link"] == "http://example.com/"

    def test_empty_link_skipped(self):
        urls = [{"link": "", "title": "T"}]
        with patch("scrape._gather_all", new=AsyncMock(return_value=[])) as mock_gather:
            result = _run_scrape_multiple(urls)

        mock_gather.assert_not_called()
        assert result == {}

    def test_non_list_input_returns_empty_dict(self):
        assert _run_scrape_multiple("not a list") == {}
        assert _run_scrape_multiple(None) == {}


# ---------------------------------------------------------------------------
# TestReturnShape
# ---------------------------------------------------------------------------

class TestReturnShape:
    def test_content_truncated_at_2000_chars(self):
        # Exceed MAX_RETURN_CHARS so the public dict is truncated with suffix
        long_text = "x" * (MAX_RETURN_CHARS + 500)
        url = "http://example.com/"

        with patch("scrape._gather_all", new=AsyncMock(return_value=[
            (url, long_text, b"data", long_text, None),
        ])):
            result = _run_scrape_multiple([{"link": url, "title": "T"}])

        assert url in result
        assert len(result[url]) <= MAX_RETURN_CHARS
        assert result[url].endswith("...(truncated)")

    def test_content_under_2000_not_truncated(self):
        short_text = "hello world"
        url = "http://example.com/"

        with patch("scrape._gather_all", new=AsyncMock(return_value=[
            (url, short_text, b"data", short_text, None),
        ])):
            result = _run_scrape_multiple([{"link": url, "title": "T"}])

        assert result[url] == short_text
        assert "truncated" not in result[url]

    def test_failed_fetch_still_in_result_dict(self):
        """A URL whose fetch failed (raw_bytes=None) still appears in the dict."""
        url = "http://example.com/fail"
        with patch("scrape._gather_all", new=AsyncMock(return_value=[
            (url, "FallbackTitle", None, None, None),
        ])):
            result = _run_scrape_multiple([{"link": url, "title": "FallbackTitle"}])

        assert url in result


# ---------------------------------------------------------------------------
# TestDownloadCap
# ---------------------------------------------------------------------------

class TestDownloadCap:
    def test_response_capped_at_1mb(self):
        """_fetch_one must not accumulate more than MAX_DOWNLOAD_BYTES."""
        resp = MagicMock()
        resp.status = 200
        resp.headers = {"Content-Type": "text/html"}
        resp.charset = "utf-8"

        # 200 chunks × 8 192 bytes = ~1.6 MB — well over the 1 MB cap
        async def iter_chunked(n: int):
            for _ in range(200):
                yield b"x" * n

        resp.content.iter_chunked = iter_chunked
        resp.__aenter__ = AsyncMock(return_value=resp)
        resp.__aexit__ = AsyncMock(return_value=False)

        session = make_session_mock(resp)
        url_data = {"link": "http://example.com/large", "title": "Large"}

        with patch.object(scrape, "RETRY_DELAYS", (0.0, 0.0, 0.0)):
            url, display_text, raw_bytes, db_text, _posted_at = run_fetch(session, url_data)

        assert raw_bytes is not None
        assert len(raw_bytes) <= MAX_DOWNLOAD_BYTES


# ---------------------------------------------------------------------------
# TestDBPersistence
# ---------------------------------------------------------------------------

class TestDBPersistence:
    def test_page_created_after_scrape(self, _db_url):
        from sqlalchemy.orm import sessionmaker
        from db.models import Page
        from db.session import get_engine

        url = "http://example.com/persist"
        body = b"<html><body>persisted content</body></html>"

        with patch("scrape._gather_all", new=AsyncMock(return_value=[
            (url, "T - persisted content", body, "persisted content", None),
        ])):
            result = _run_scrape_multiple([{"link": url, "title": "T"}])

        assert url in result

        SM = sessionmaker(bind=get_engine(SCRAPE_TEST_DB_URL))
        s = SM()
        page = s.query(Page).filter_by(url=url).first()
        s.close()

        assert page is not None
        assert page.raw_content_hash == hashlib.sha256(body).hexdigest()
        assert page.cleaned_text == "persisted content"

    def test_duplicate_content_hash_not_reinserted(self, _db_url):
        from sqlalchemy.orm import sessionmaker
        from db.models import Page
        from db.session import get_engine

        body = b"<html><body>identical content</body></html>"
        url1 = "http://example.com/copy-a"
        url2 = "http://example.com/copy-b"

        with patch("scrape._gather_all", new=AsyncMock(return_value=[
            (url1, "T - identical content", body, "identical content", None),
        ])):
            _run_scrape_multiple([{"link": url1, "title": "T"}])

        with patch("scrape._gather_all", new=AsyncMock(return_value=[
            (url2, "T - identical content", body, "identical content", None),
        ])):
            _run_scrape_multiple([{"link": url2, "title": "T"}])

        SM = sessionmaker(bind=get_engine(SCRAPE_TEST_DB_URL))
        s = SM()
        count = s.query(Page).count()
        s.close()

        # Second scrape had the same SHA-256 hash → deduped → still only 1 page
        assert count == 1

    def test_source_created_for_onion_url(self, _db_url):
        from sqlalchemy.orm import sessionmaker
        from db.models import Source
        from db.session import get_engine

        url = "http://exampleonion123.onion/page"
        body = b"<html><body>onion content</body></html>"

        with patch("scrape._gather_all", new=AsyncMock(return_value=[
            (url, "T - onion content", body, "onion content", None),
        ])):
            _run_scrape_multiple([{"link": url, "title": "T"}])

        SM = sessionmaker(bind=get_engine(SCRAPE_TEST_DB_URL))
        s = SM()
        source = s.query(Source).first()
        s.close()

        assert source is not None
        assert source.onion_address == "exampleonion123.onion"

    def test_no_source_for_clearnet_url(self, _db_url):
        from sqlalchemy.orm import sessionmaker
        from db.models import Source
        from db.session import get_engine

        url = "http://example.com/clearnet"
        body = b"<html><body>clearnet</body></html>"

        with patch("scrape._gather_all", new=AsyncMock(return_value=[
            (url, "T - clearnet", body, "clearnet", None),
        ])):
            _run_scrape_multiple([{"link": url, "title": "T"}])

        SM = sessionmaker(bind=get_engine(SCRAPE_TEST_DB_URL))
        s = SM()
        count = s.query(Source).count()
        s.close()

        assert count == 0


# ---------------------------------------------------------------------------
# TestDBGracefulDegradation
# ---------------------------------------------------------------------------

class TestDBGracefulDegradation:
    def test_works_without_database_url(self, monkeypatch):
        monkeypatch.setattr("config.DATABASE_URL", None)

        with patch("scrape._gather_all", new=AsyncMock(return_value=[
            ("http://example.com/", "T - text", b"data", "text", None),
        ])):
            result = _run_scrape_multiple([{"link": "http://example.com/", "title": "T"}])

        assert isinstance(result, dict)
        assert "http://example.com/" in result

    def test_db_error_does_not_break_scraping(self, monkeypatch):
        monkeypatch.setattr("config.DATABASE_URL", SCRAPE_TEST_DB_URL)

        with patch("scrape._gather_all", new=AsyncMock(return_value=[
            ("http://example.com/", "T - text", b"data", "text", None),
        ])), patch("db.session.get_session", side_effect=RuntimeError("DB is down")):
            result = _run_scrape_multiple([{"link": "http://example.com/", "title": "T"}])

        assert isinstance(result, dict)
        assert "http://example.com/" in result


# ---------------------------------------------------------------------------
# TestProxyRouting
# ---------------------------------------------------------------------------

class TestProxyRouting:
    def test_build_proxy_url_uses_config(self):
        url = _build_proxy_url()
        assert url == f"socks5h://{TOR_PROXY_HOST}:{TOR_PROXY_PORT}"
        assert url.startswith("socks5h://")

    def test_is_onion_detects_onion_hostnames(self):
        assert _is_onion("http://abc123xyz.onion/page") is True
        assert _is_onion("http://example.com/") is False
        assert _is_onion("https://sub.abc.onion/path") is True
        assert _is_onion("") is False

    def test_tor_session_proxy_config(self):
        session = get_tor_session()
        expected = f"socks5h://{TOR_PROXY_HOST}:{TOR_PROXY_PORT}"
        assert session.proxies.get("http") == expected
        assert session.proxies.get("https") == expected

    def test_onion_url_uses_proxy_connector(self):
        """aiohttp-socks uses python_socks, which only parses socks5:// (not socks5h://).
        Remote DNS for .onion is enabled via rdns=True."""
        captured: list[tuple[str, dict]] = []

        def capture(url, **kwargs):
            captured.append((url, kwargs))
            return MagicMock()

        mock_cs = AsyncMock()
        mock_cs.__aenter__ = AsyncMock(return_value=mock_cs)
        mock_cs.__aexit__ = AsyncMock(return_value=False)

        with patch("scrape.ProxyConnector.from_url", side_effect=capture), \
             patch("aiohttp.ClientSession", return_value=mock_cs), \
             patch("scrape._fetch_one", new=AsyncMock(
                 return_value=("http://test.onion/", "T", b"d", "t", None)
             )):
            _run_scrape_multiple([{"link": "http://test.onion/page", "title": "T"}])

        assert len(captured) == 1
        url, kwargs = captured[0]
        assert url.startswith("socks5://")
        assert kwargs.get("rdns") is True


# ---------------------------------------------------------------------------
# TestSSRFPrevention
# ---------------------------------------------------------------------------


class TestSSRFPrevention:
    def test_onion_always_allowed(self):
        from scrape import is_safe_url

        assert is_safe_url("http://abcdefghijklmnopqrstuvwxyz2345.onion/path") is True

    def test_loopback_ipv4_blocked(self):
        from scrape import is_safe_url

        assert is_safe_url("http://127.0.0.1:80/") is False

    def test_private_class_a_blocked(self):
        from scrape import is_safe_url

        assert is_safe_url("http://10.0.0.1/") is False

    def test_private_class_c_blocked(self):
        from scrape import is_safe_url

        assert is_safe_url("http://192.168.0.10/") is False

    def test_metadata_hostname_blocked(self):
        from scrape import is_safe_url

        assert is_safe_url("http://metadata.google.internal/") is False

    def test_validate_urls_filters_unsafe(self):
        from scrape import validate_urls_for_scraping

        safe, blocked = validate_urls_for_scraping(
            [
                {"link": "http://192.168.0.1/", "title": "a"},
                {"link": "http://example.com/", "title": "b"},
            ]
        )
        assert len(blocked) == 1
        assert len(safe) == 1
        assert safe[0]["link"] == "http://example.com/"

    def test_extract_post_timestamp_never_raises(self):
        from scrape import extract_post_timestamp

        assert extract_post_timestamp("") is None

    def test_extract_post_timestamp_none_input(self):
        from scrape import extract_post_timestamp

        assert extract_post_timestamp(None) is None  # type: ignore[arg-type]

    def test_public_clearnet_allowed(self):
        from scrape import is_safe_url

        assert is_safe_url("https://example.com/page") is True

    def test_link_local_169_blocked(self):
        from scrape import is_safe_url

        assert is_safe_url("http://169.254.169.254/latest/meta-data/") is False
