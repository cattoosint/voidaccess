"""
tests/test_sources_enrichment.py — Threat intel enrichment (OTX + abuse.ch).
"""

from __future__ import annotations

import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def _resp_json(data: dict, status: int = 200) -> MagicMock:
    r = MagicMock()
    r.status = status
    r.__aenter__ = AsyncMock(return_value=r)
    r.__aexit__ = AsyncMock(return_value=False)
    r.json = AsyncMock(return_value=data)
    return r


def _mock_client_session() -> MagicMock:
    """Canned aiohttp session: abuse.ch POSTs return sample rows (no real HTTP)."""
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)

    def _get(url: str, **kwargs):
        u = str(url)
        if "search/pulses" in u:
            return _resp_json({"results": []})
        if "/pulses/" in u and "indicators" in u:
            return _resp_json({"results": []})
        return _resp_json({}, status=404)

    def _post(url: str, **kwargs):
        u = str(url)
        if "mb-api" in u:
            return _resp_json(
                {
                    "query_status": "ok",
                    "data": [
                        {
                            "sha256_hash": "aa" * 32,
                            "signature": "TestSig",
                            "tags": ["exe"],
                            "first_seen": "2021-01-01",
                            "reporter": "abuse_ch",
                        }
                    ],
                }
            )
        if "threatfox" in u:
            return _resp_json(
                {
                    "query_status": "ok",
                    "data": [
                        {
                            "ioc": "1.2.3.4:443",
                            "ioc_type": "ip:port",
                            "malware_printable": "TestMalware",
                            "confidence_level": 50,
                            "tags": ["t"],
                        }
                    ],
                }
            )
        if "urlhaus" in u:
            return _resp_json(
                {
                    "query_status": "ok",
                    "urls": [
                        {
                            "url": "http://evil.test/payload",
                            "threat": "malware_download",
                            "tags": ["u"],
                        }
                    ],
                }
            )
        return _resp_json({}, status=404)

    session.get = MagicMock(side_effect=_get)
    session.post = MagicMock(side_effect=_post)
    return session


class TestSourcesEnrichment(unittest.TestCase):
    """Tests for sources/enrichment.py"""

    def test_is_onion_url(self):
        from sources.enrichment import is_onion_url

        self.assertTrue(
            is_onion_url(
                "http://zqktlwiuavvvqqt4ybvgvi7tyo4hjl5xgfuvpdf6otjiycgwqbym2qad.onion/wiki"
            )
        )
        self.assertTrue(
            is_onion_url(
                "https://example123456789012345678901234567890abcdefgh.onion/path"
            )
        )
        self.assertFalse(is_onion_url("https://example.com/path"))
        self.assertFalse(is_onion_url(""))

    def test_otx_pulse_to_page(self):
        from sources.enrichment import otx_pulse_to_page

        pulse = {
            "pulse_id": "p1",
            "title": "Test Pulse",
            "description": "Desc",
            "tags": ["tag1"],
            "malware_families": [{"display_name": "FamilyX"}],
            "attack_ids": ["T1059"],
            "indicators": [
                {"type": "domain", "value": "bad.com", "description": "c2"}
            ],
        }
        page = otx_pulse_to_page(pulse)
        self.assertIn("link", page)
        self.assertIn("content", page)
        self.assertGreater(len(page["content"].strip()), 0)
        self.assertEqual(page["status"], 200)
        self.assertEqual(page["source"], "alienvault_otx")
        self.assertIn("bad.com", page["content"])

    def test_abusech_to_pages_with_mock_data(self):
        from sources.enrichment import abusech_to_pages

        mb = [
            {
                "malware_family": "Z",
                "sha256": "f" * 64,
                "tags": ["a"],
                "reporter": "r",
                "first_seen": "d",
            }
        ]
        tf = [
            {
                "ioc_type": "domain",
                "ioc_value": "d.com",
                "malware_printable": "M",
                "confidence": 0.5,
                "tags": ["t"],
            }
        ]
        uh = [{"url": "http://x/y", "threat": "malware_download", "tags": ["u"]}]
        pages = abusech_to_pages(mb, tf, uh)
        self.assertEqual(len(pages), 3)
        for p in pages:
            self.assertIn("link", p)
            self.assertIn("content", p)
            self.assertIn("status", p)
            self.assertIn("source", p)
            self.assertEqual(p["status"], 200)

    def test_enrich_investigation_no_otx_key_abuse_ch_mocked(self):
        """No OTX key → no OTX pages; Abuse.ch paths still run (HTTP mocked)."""
        from sources import enrichment as enr

        prev = os.environ.pop("ABUSECH_API_KEY", None)
        try:
            with patch.object(
                enr.aiohttp,
                "ClientSession",
                return_value=_mock_client_session(),
            ):
                pages = asyncio.run(
                    enr.enrich_investigation("test query", otx_api_key="")
                )
        finally:
            if prev is not None:
                os.environ["ABUSECH_API_KEY"] = prev

        otx_pages = [p for p in pages if p.get("source") == "alienvault_otx"]
        self.assertEqual(len(otx_pages), 0)
        self.assertGreaterEqual(len(pages), 3)
        for p in pages:
            for key in ("link", "content", "status", "source"):
                self.assertIn(key, p)

    def test_enrich_investigation_exported_from_sources_package(self):
        from sources import enrich_investigation

        self.assertTrue(callable(enrich_investigation))


if __name__ == "__main__":
    unittest.main()
