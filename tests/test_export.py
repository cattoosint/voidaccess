"""
tests/test_export.py — Tests for Phase 5 export module.

Test classes
------------
TestStixIndicator     — export/stix.py: entity_to_stix_indicator
TestStixMalware       — export/stix.py: entity_to_stix_malware
TestStixThreatActor   — export/stix.py: entity_to_stix_threat_actor
TestStixBundle        — export/stix.py: investigation_to_stix_bundle, bundle_to_*
TestStixUnavailable   — export/stix.py: graceful degradation when stix2 absent
TestMispEvent         — export/misp.py: investigation_to_misp_event
TestMispJson          — export/misp.py: misp_event_to_json
TestSigmaRules        — export/sigma.py: entities_to_sigma_rules
TestSigmaYaml         — export/sigma.py: sigma_rule_to_yaml
"""

from __future__ import annotations

import json
import os
import sys
import types
import unittest
from dataclasses import dataclass
from typing import Optional
from unittest.mock import MagicMock, patch

import yaml

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


# ---------------------------------------------------------------------------
# Minimal NormalizedEntity stand-in (avoids importing extractor in isolation)
# ---------------------------------------------------------------------------

@dataclass
class _Entity:
    entity_type: str
    value: str
    confidence: float = 1.0
    source_url: str = "http://example.onion/page"
    page_id: Optional[int] = None
    context: str = ""


# ===========================================================================
# TestStixIndicator
# ===========================================================================


class TestStixIndicator(unittest.TestCase):

    def test_bitcoin_address_pattern(self):
        from export.stix import entity_to_stix_indicator
        e = _Entity("BITCOIN_ADDRESS", "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh")
        indicator = entity_to_stix_indicator(e)
        if indicator is None:
            self.skipTest("stix2 not installed")
        self.assertIn("cryptocurrency-wallet:address", indicator.pattern)
        self.assertIn(e.value, indicator.pattern)

    def test_ethereum_address_pattern(self):
        from export.stix import entity_to_stix_indicator
        e = _Entity("ETHEREUM_ADDRESS", "0x742d35Cc6634C0532925a3b844Bc454e4438f44e")
        indicator = entity_to_stix_indicator(e)
        if indicator is None:
            self.skipTest("stix2 not installed")
        self.assertIn("cryptocurrency-wallet:address", indicator.pattern)

    def test_monero_address_pattern(self):
        from export.stix import entity_to_stix_indicator
        e = _Entity("MONERO_ADDRESS", "4AdUndXHHZ6cfufTMvppY6JwXNouMBzSkbLYfpAV5Usx3skxNgYeYTRj5UzqtReoS44qo9mtmXCqY45DJ852K2Jku2kgE3f")
        indicator = entity_to_stix_indicator(e)
        if indicator is None:
            self.skipTest("stix2 not installed")
        self.assertIn("cryptocurrency-wallet:address", indicator.pattern)

    def test_email_address_pattern(self):
        from export.stix import entity_to_stix_indicator
        e = _Entity("EMAIL_ADDRESS", "threat@example.onion")
        indicator = entity_to_stix_indicator(e)
        if indicator is None:
            self.skipTest("stix2 not installed")
        self.assertIn("email-message:from_ref.value", indicator.pattern)
        self.assertIn(e.value, indicator.pattern)

    def test_onion_url_pattern(self):
        from export.stix import entity_to_stix_indicator
        e = _Entity("ONION_URL", "http://abcdefghijklmnop.onion/forum")
        indicator = entity_to_stix_indicator(e)
        if indicator is None:
            self.skipTest("stix2 not installed")
        self.assertIn("url:value", indicator.pattern)

    def test_ip_address_pattern(self):
        from export.stix import entity_to_stix_indicator
        e = _Entity("IP_ADDRESS", "185.220.101.1")
        indicator = entity_to_stix_indicator(e)
        if indicator is None:
            self.skipTest("stix2 not installed")
        self.assertIn("ipv4-addr:value", indicator.pattern)
        self.assertIn("185.220.101.1", indicator.pattern)

    def test_cve_pattern(self):
        from export.stix import entity_to_stix_indicator
        e = _Entity("CVE_NUMBER", "CVE-2024-12345")
        indicator = entity_to_stix_indicator(e)
        if indicator is None:
            self.skipTest("stix2 not installed")
        self.assertIn("vulnerability:name", indicator.pattern)

    def test_malware_family_pattern(self):
        from export.stix import entity_to_stix_indicator
        e = _Entity("MALWARE_FAMILY", "LockBit")
        indicator = entity_to_stix_indicator(e)
        if indicator is None:
            self.skipTest("stix2 not installed")
        self.assertIn("malware:name", indicator.pattern)

    def test_returns_none_for_pgp_key(self):
        from export.stix import entity_to_stix_indicator
        e = _Entity("PGP_KEY_BLOCK", "AABBCCDD")
        result = entity_to_stix_indicator(e)
        # Should be None regardless of stix2 availability for unmapped type
        self.assertIsNone(result)

    def test_returns_none_for_paste_url(self):
        from export.stix import entity_to_stix_indicator
        e = _Entity("PASTE_URL", "https://pastebin.com/abc123")
        result = entity_to_stix_indicator(e)
        self.assertIsNone(result)

    def test_confidence_mapping_1_0(self):
        from export.stix import entity_to_stix_indicator
        e = _Entity("IP_ADDRESS", "185.220.101.2", confidence=1.0)
        indicator = entity_to_stix_indicator(e)
        if indicator is None:
            self.skipTest("stix2 not installed")
        self.assertEqual(indicator.confidence, 100)

    def test_confidence_mapping_0_8(self):
        from export.stix import entity_to_stix_indicator
        e = _Entity("MALWARE_FAMILY", "Emotet", confidence=0.8)
        indicator = entity_to_stix_indicator(e)
        if indicator is None:
            self.skipTest("stix2 not installed")
        self.assertEqual(indicator.confidence, 80)

    def test_confidence_mapping_0_7(self):
        from export.stix import entity_to_stix_indicator
        e = _Entity("ONION_URL", "http://xyz.onion/", confidence=0.7)
        indicator = entity_to_stix_indicator(e)
        if indicator is None:
            self.skipTest("stix2 not installed")
        self.assertEqual(indicator.confidence, 70)


# ===========================================================================
# TestStixMalware
# ===========================================================================


class TestStixMalware(unittest.TestCase):

    def test_malware_family_returns_malware_object(self):
        from export.stix import entity_to_stix_malware
        e = _Entity("MALWARE_FAMILY", "Emotet")
        result = entity_to_stix_malware(e)
        if result is None:
            # Could be stix2 not installed OR wrong type — differentiate
            import sys
            if "stix2" not in sys.modules:
                self.skipTest("stix2 not installed")
        self.assertIsNotNone(result)
        self.assertTrue(result.is_family)
        self.assertEqual(result.name, "Emotet")

    def test_ransomware_group_returns_malware_object(self):
        from export.stix import entity_to_stix_malware
        e = _Entity("RANSOMWARE_GROUP", "LockBit")
        result = entity_to_stix_malware(e)
        if result is None:
            import sys
            if "stix2" not in sys.modules:
                self.skipTest("stix2 not installed")
        self.assertIsNotNone(result)
        self.assertTrue(result.is_family)

    def test_returns_none_for_ip_address(self):
        from export.stix import entity_to_stix_malware
        e = _Entity("IP_ADDRESS", "185.220.101.3")
        result = entity_to_stix_malware(e)
        self.assertIsNone(result)

    def test_returns_none_for_bitcoin(self):
        from export.stix import entity_to_stix_malware
        e = _Entity("BITCOIN_ADDRESS", "bc1qtest")
        result = entity_to_stix_malware(e)
        self.assertIsNone(result)


# ===========================================================================
# TestStixThreatActor
# ===========================================================================


class TestStixThreatActor(unittest.TestCase):

    def test_threat_actor_handle_returns_threat_actor(self):
        from export.stix import entity_to_stix_threat_actor
        e = _Entity("THREAT_ACTOR_HANDLE", "DarkKnight99")
        result = entity_to_stix_threat_actor(e)
        if result is None:
            import sys
            if "stix2" not in sys.modules:
                self.skipTest("stix2 not installed")
        self.assertIsNotNone(result)
        self.assertEqual(result.name, "DarkKnight99")
        self.assertIn("DarkKnight99", result.aliases)

    def test_returns_none_for_malware(self):
        from export.stix import entity_to_stix_threat_actor
        e = _Entity("MALWARE_FAMILY", "Ryuk")
        result = entity_to_stix_threat_actor(e)
        self.assertIsNone(result)

    def test_returns_none_for_ip(self):
        from export.stix import entity_to_stix_threat_actor
        e = _Entity("IP_ADDRESS", "1.2.3.4")
        result = entity_to_stix_threat_actor(e)
        self.assertIsNone(result)


# ===========================================================================
# TestStixBundle
# ===========================================================================


class TestStixBundle(unittest.TestCase):

    def _mock_entities(self):
        return [
            _Entity("IP_ADDRESS", "185.220.101.4"),
            _Entity("MALWARE_FAMILY", "Ryuk"),
            _Entity("THREAT_ACTOR_HANDLE", "hacker42"),
        ]

    @patch("export.stix._load_entities_for_investigation")
    @patch("export.stix._build_stix_relationships", return_value=[])
    def test_bundle_contains_objects(self, mock_rels, mock_load):
        mock_load.return_value = self._mock_entities()
        from export.stix import investigation_to_stix_bundle
        bundle = investigation_to_stix_bundle("00000000-0000-0000-0000-000000000001")
        if bundle is None:
            self.skipTest("stix2 not installed")
        d = bundle.serialize()
        self.assertIn("bundle", d.lower())

    @patch("export.stix._load_entities_for_investigation")
    @patch("export.stix._build_stix_relationships", return_value=[])
    def test_bundle_to_dict_returns_plain_dict(self, mock_rels, mock_load):
        mock_load.return_value = self._mock_entities()
        from export.stix import investigation_to_stix_bundle, bundle_to_dict
        bundle = investigation_to_stix_bundle("00000000-0000-0000-0000-000000000002")
        if bundle is None:
            self.skipTest("stix2 not installed")
        d = bundle_to_dict(bundle)
        self.assertIsInstance(d, dict)
        # Must be plain dict — all values JSON-native
        raw = json.dumps(d)  # would raise if any stix2 objects remain
        self.assertIn("bundle", raw.lower())

    @patch("export.stix._load_entities_for_investigation", return_value=[])
    def test_empty_bundle_on_no_entities(self, mock_load):
        from export.stix import investigation_to_stix_bundle, bundle_to_dict
        bundle = investigation_to_stix_bundle("00000000-0000-0000-0000-000000000003")
        if bundle is None:
            self.skipTest("stix2 not installed")
        d = bundle_to_dict(bundle)
        self.assertIsInstance(d, dict)

    @patch("export.stix._load_entities_for_investigation")
    @patch("export.stix._build_stix_relationships", return_value=[])
    def test_bundle_to_json_is_valid_json(self, mock_rels, mock_load):
        mock_load.return_value = self._mock_entities()
        from export.stix import investigation_to_stix_bundle, bundle_to_json
        bundle = investigation_to_stix_bundle("00000000-0000-0000-0000-000000000004")
        if bundle is None:
            self.skipTest("stix2 not installed")
        raw = bundle_to_json(bundle)
        self.assertIsInstance(raw, str)
        parsed = json.loads(raw)
        self.assertIsInstance(parsed, dict)


# ===========================================================================
# TestStixUnavailable
# ===========================================================================


class TestStixUnavailable(unittest.TestCase):
    """
    Verify graceful degradation when stix2 is not installed.
    We temporarily hide the module from sys.modules.
    """

    def setUp(self):
        # Stash real stix2 if present
        self._real_stix2 = sys.modules.get("stix2")
        sys.modules["stix2"] = None  # type: ignore
        # Force re-evaluation of _STIX2_AVAILABLE in export.stix
        import importlib
        import export.stix as stix_mod
        stix_mod._STIX2_AVAILABLE = False
        stix_mod.stix2 = None

    def tearDown(self):
        if self._real_stix2 is not None:
            sys.modules["stix2"] = self._real_stix2
        else:
            sys.modules.pop("stix2", None)
        import export.stix as stix_mod
        try:
            import stix2
            stix_mod._STIX2_AVAILABLE = True
            stix_mod.stix2 = stix2
        except ImportError:
            stix_mod._STIX2_AVAILABLE = False

    def test_indicator_returns_none_no_raise(self):
        import export.stix as stix_mod
        e = _Entity("IP_ADDRESS", "1.2.3.4")
        result = stix_mod.entity_to_stix_indicator(e)
        self.assertIsNone(result)

    def test_malware_returns_none_no_raise(self):
        import export.stix as stix_mod
        e = _Entity("MALWARE_FAMILY", "Ryuk")
        result = stix_mod.entity_to_stix_malware(e)
        self.assertIsNone(result)

    def test_threat_actor_returns_none_no_raise(self):
        import export.stix as stix_mod
        e = _Entity("THREAT_ACTOR_HANDLE", "actor1")
        result = stix_mod.entity_to_stix_threat_actor(e)
        self.assertIsNone(result)

    def test_bundle_returns_none_no_raise(self):
        import export.stix as stix_mod
        result = stix_mod.investigation_to_stix_bundle("00000000-0000-0000-0000-000000000099")
        self.assertIsNone(result)

    def test_bundle_to_json_returns_string_no_raise(self):
        import export.stix as stix_mod
        result = stix_mod.bundle_to_json(None)
        self.assertIsInstance(result, str)

    def test_bundle_to_dict_returns_dict_no_raise(self):
        import export.stix as stix_mod
        result = stix_mod.bundle_to_dict(None)
        self.assertIsInstance(result, dict)


# ===========================================================================
# TestMispEvent
# ===========================================================================


class TestMispEvent(unittest.TestCase):

    def _make_investigation(self):
        from datetime import datetime, timezone
        inv = MagicMock()
        inv.query = "test ransomware query"
        inv.created_at = datetime(2025, 1, 15, tzinfo=timezone.utc)
        return inv

    @patch("export.misp._load_investigation_and_entities")
    def test_bitcoin_attribute_type(self, mock_load):
        entities = [_Entity("BITCOIN_ADDRESS", "bc1qtest123")]
        mock_load.return_value = (self._make_investigation(), entities)
        from export.misp import investigation_to_misp_event
        event = investigation_to_misp_event("00000000-0000-0000-0000-000000000001")
        attrs = event["Event"]["Attribute"]
        self.assertEqual(len(attrs), 1)
        self.assertEqual(attrs[0]["type"], "btc")
        self.assertEqual(attrs[0]["category"], "Financial fraud")

    @patch("export.misp._load_investigation_and_entities")
    def test_ethereum_attribute_type(self, mock_load):
        entities = [_Entity("ETHEREUM_ADDRESS", "0xdeadbeef")]
        mock_load.return_value = (self._make_investigation(), entities)
        from export.misp import investigation_to_misp_event
        event = investigation_to_misp_event("00000000-0000-0000-0000-000000000002")
        attrs = event["Event"]["Attribute"]
        self.assertEqual(attrs[0]["type"], "other")
        self.assertEqual(attrs[0]["category"], "Financial fraud")

    @patch("export.misp._load_investigation_and_entities")
    def test_ip_attribute_type(self, mock_load):
        entities = [_Entity("IP_ADDRESS", "185.220.101.5")]
        mock_load.return_value = (self._make_investigation(), entities)
        from export.misp import investigation_to_misp_event
        event = investigation_to_misp_event("00000000-0000-0000-0000-000000000003")
        attrs = event["Event"]["Attribute"]
        self.assertEqual(attrs[0]["type"], "ip-dst")

    @patch("export.misp._load_investigation_and_entities")
    def test_cve_attribute_type(self, mock_load):
        entities = [_Entity("CVE_NUMBER", "CVE-2024-99999")]
        mock_load.return_value = (self._make_investigation(), entities)
        from export.misp import investigation_to_misp_event
        event = investigation_to_misp_event("00000000-0000-0000-0000-000000000004")
        attrs = event["Event"]["Attribute"]
        self.assertEqual(attrs[0]["type"], "vulnerability")
        self.assertEqual(attrs[0]["category"], "External analysis")

    @patch("export.misp._load_investigation_and_entities")
    def test_malware_attribute_type(self, mock_load):
        entities = [_Entity("MALWARE_FAMILY", "Emotet")]
        mock_load.return_value = (self._make_investigation(), entities)
        from export.misp import investigation_to_misp_event
        event = investigation_to_misp_event("00000000-0000-0000-0000-000000000005")
        attrs = event["Event"]["Attribute"]
        self.assertEqual(attrs[0]["type"], "malware-type")

    @patch("export.misp._load_investigation_and_entities")
    def test_threat_actor_attribute_type(self, mock_load):
        entities = [_Entity("THREAT_ACTOR_HANDLE", "darkactor")]
        mock_load.return_value = (self._make_investigation(), entities)
        from export.misp import investigation_to_misp_event
        event = investigation_to_misp_event("00000000-0000-0000-0000-000000000006")
        attrs = event["Event"]["Attribute"]
        self.assertEqual(attrs[0]["type"], "threat-actor")
        self.assertEqual(attrs[0]["category"], "Attribution")

    @patch("export.misp._load_investigation_and_entities")
    def test_wallet_entities_have_to_ids_true(self, mock_load):
        entities = [
            _Entity("BITCOIN_ADDRESS", "bc1qtest"),
            _Entity("ETHEREUM_ADDRESS", "0xtest"),
            _Entity("MONERO_ADDRESS", "4AdUtest"),
        ]
        mock_load.return_value = (self._make_investigation(), entities)
        from export.misp import investigation_to_misp_event
        event = investigation_to_misp_event("00000000-0000-0000-0000-000000000007")
        attrs = event["Event"]["Attribute"]
        for attr in attrs:
            self.assertTrue(attr["to_ids"], f"Expected to_ids=True for {attr['type']}")

    @patch("export.misp._load_investigation_and_entities")
    def test_ip_has_to_ids_true(self, mock_load):
        entities = [_Entity("IP_ADDRESS", "10.0.0.1")]
        mock_load.return_value = (self._make_investigation(), entities)
        from export.misp import investigation_to_misp_event
        event = investigation_to_misp_event("00000000-0000-0000-0000-000000000008")
        attrs = event["Event"]["Attribute"]
        self.assertTrue(attrs[0]["to_ids"])

    @patch("export.misp._load_investigation_and_entities")
    def test_threat_actor_has_to_ids_false(self, mock_load):
        entities = [_Entity("THREAT_ACTOR_HANDLE", "actor")]
        mock_load.return_value = (self._make_investigation(), entities)
        from export.misp import investigation_to_misp_event
        event = investigation_to_misp_event("00000000-0000-0000-0000-000000000009")
        attrs = event["Event"]["Attribute"]
        self.assertFalse(attrs[0]["to_ids"])

    @patch("export.misp._load_investigation_and_entities")
    def test_malware_has_to_ids_false(self, mock_load):
        entities = [_Entity("MALWARE_FAMILY", "Ryuk")]
        mock_load.return_value = (self._make_investigation(), entities)
        from export.misp import investigation_to_misp_event
        event = investigation_to_misp_event("00000000-0000-0000-0000-000000000010")
        attrs = event["Event"]["Attribute"]
        self.assertFalse(attrs[0]["to_ids"])

    @patch("export.misp._load_investigation_and_entities")
    def test_investigation_not_found_returns_empty_attributes(self, mock_load):
        mock_load.return_value = (None, [])
        from export.misp import investigation_to_misp_event
        event = investigation_to_misp_event("00000000-0000-0000-0000-000000000099")
        self.assertEqual(event["Event"]["info"], "Not found")
        self.assertEqual(event["Event"]["Attribute"], [])

    @patch("export.misp._load_investigation_and_entities")
    def test_event_structure_fields(self, mock_load):
        mock_load.return_value = (self._make_investigation(), [])
        from export.misp import investigation_to_misp_event
        event = investigation_to_misp_event("00000000-0000-0000-0000-000000000011")
        e = event["Event"]
        self.assertIn("info", e)
        self.assertIn("date", e)
        self.assertIn("threat_level_id", e)
        self.assertIn("analysis", e)
        self.assertIn("distribution", e)
        self.assertIn("Attribute", e)

    @patch("export.misp._load_investigation_and_entities")
    def test_unsupported_entity_type_skipped(self, mock_load):
        entities = [_Entity("PHONE_NUMBER", "+12025551234")]
        mock_load.return_value = (self._make_investigation(), entities)
        from export.misp import investigation_to_misp_event
        event = investigation_to_misp_event("00000000-0000-0000-0000-000000000012")
        self.assertEqual(event["Event"]["Attribute"], [])


# ===========================================================================
# TestMispJson
# ===========================================================================


class TestMispJson(unittest.TestCase):

    def test_json_output_is_valid_string(self):
        from export.misp import misp_event_to_json
        event = {"Event": {"info": "test", "Attribute": []}}
        result = misp_event_to_json(event)
        self.assertIsInstance(result, str)
        parsed = json.loads(result)
        self.assertEqual(parsed["Event"]["info"], "test")

    def test_json_pretty_printed(self):
        from export.misp import misp_event_to_json
        event = {"Event": {"info": "test", "Attribute": [{"type": "btc", "value": "abc"}]}}
        result = misp_event_to_json(event)
        # Pretty-printed: should contain newlines and spaces
        self.assertIn("\n", result)

    def test_empty_event_json(self):
        from export.misp import misp_event_to_json
        result = misp_event_to_json({"Event": {"info": "Not found", "Attribute": []}})
        parsed = json.loads(result)
        self.assertEqual(parsed["Event"]["Attribute"], [])


# ===========================================================================
# TestSigmaRules
# ===========================================================================


class TestSigmaRules(unittest.TestCase):

    def test_ip_entity_produces_rule(self):
        from export.sigma import entities_to_sigma_rules
        entities = [_Entity("IP_ADDRESS", "185.220.101.6")]
        rules = entities_to_sigma_rules(entities)
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0]["logsource"]["category"], "network")

    def test_ip_rule_has_network_logsource(self):
        from export.sigma import entities_to_sigma_rules
        e = _Entity("IP_ADDRESS", "185.220.101.7")
        rules = entities_to_sigma_rules([e])
        self.assertIn("network", rules[0]["logsource"]["category"])

    def test_malware_family_produces_rule(self):
        from export.sigma import entities_to_sigma_rules
        e = _Entity("MALWARE_FAMILY", "Emotet")
        rules = entities_to_sigma_rules([e])
        self.assertEqual(len(rules), 1)
        self.assertIn("Emotet", rules[0]["title"])

    def test_ransomware_group_produces_rule(self):
        from export.sigma import entities_to_sigma_rules
        e = _Entity("RANSOMWARE_GROUP", "LockBit")
        rules = entities_to_sigma_rules([e])
        self.assertEqual(len(rules), 1)

    def test_email_address_produces_no_rule(self):
        from export.sigma import entities_to_sigma_rules
        e = _Entity("EMAIL_ADDRESS", "hacker@evil.onion")
        rules = entities_to_sigma_rules([e])
        self.assertEqual(len(rules), 0)

    def test_pgp_key_produces_no_rule(self):
        from export.sigma import entities_to_sigma_rules
        e = _Entity("PGP_KEY_BLOCK", "DEADBEEF")
        rules = entities_to_sigma_rules([e])
        self.assertEqual(len(rules), 0)

    def test_bitcoin_address_produces_no_rule(self):
        from export.sigma import entities_to_sigma_rules
        e = _Entity("BITCOIN_ADDRESS", "bc1qtest")
        rules = entities_to_sigma_rules([e])
        self.assertEqual(len(rules), 0)

    def test_cve_produces_rule(self):
        from export.sigma import entities_to_sigma_rules
        e = _Entity("CVE_NUMBER", "CVE-2024-12345")
        rules = entities_to_sigma_rules([e])
        self.assertEqual(len(rules), 1)

    def test_onion_url_produces_rule(self):
        from export.sigma import entities_to_sigma_rules
        e = _Entity("ONION_URL", "http://evil.onion/c2")
        rules = entities_to_sigma_rules([e])
        self.assertEqual(len(rules), 1)

    def test_rule_has_required_fields(self):
        from export.sigma import entities_to_sigma_rules
        e = _Entity("IP_ADDRESS", "8.8.8.8")
        rules = entities_to_sigma_rules([e])
        required = {"title", "id", "status", "description", "detection", "level"}
        for field in required:
            self.assertIn(field, rules[0])

    def test_rule_id_is_uuid4_format(self):
        import uuid as _uuid
        from export.sigma import entities_to_sigma_rules
        e = _Entity("MALWARE_FAMILY", "TrickBot")
        rules = entities_to_sigma_rules([e])
        rule_id = rules[0]["id"]
        # Should parse as UUID without error
        _uuid.UUID(rule_id)

    def test_llm_none_returns_base_rule_no_api_call(self):
        from export.sigma import entities_to_sigma_rules
        e = _Entity("IP_ADDRESS", "1.2.3.5")
        # llm=None is default — no LLM call, base rule returned
        rules = entities_to_sigma_rules([e], llm=None)
        self.assertEqual(len(rules), 1)
        self.assertIsNotNone(rules[0].get("description"))

    def test_llm_fails_json_returns_base_rule_unchanged(self):
        from export.sigma import entities_to_sigma_rules
        e = _Entity("IP_ADDRESS", "1.2.3.6")

        # Mock LLM that returns invalid JSON
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "this is not json {{{"
        mock_llm.invoke.return_value = mock_response

        rules = entities_to_sigma_rules([e], llm=mock_llm)
        self.assertEqual(len(rules), 1)
        # Should return base rule unchanged — IP value is in title or description
        combined = rules[0].get("title", "") + rules[0].get("description", "")
        self.assertIn("1.2.3.6", combined)

    def test_llm_enriches_rule_when_valid(self):
        from export.sigma import entities_to_sigma_rules
        e = _Entity("MALWARE_FAMILY", "Cobalt Strike")

        enriched_fields = {
            "description": "Enriched description from LLM",
            "tags": ["attack.t1071", "attack.c2"],
            "falsepositives": ["Legitimate red team activity"],
        }
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = json.dumps(enriched_fields)
        mock_llm.invoke.return_value = mock_response

        rules = entities_to_sigma_rules([e], llm=mock_llm)
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0]["description"], "Enriched description from LLM")
        self.assertEqual(rules[0]["tags"], ["attack.t1071", "attack.c2"])


# ===========================================================================
# TestSigmaYaml
# ===========================================================================


class TestSigmaYaml(unittest.TestCase):

    def _sample_rule(self) -> dict:
        return {
            "title": "Test Rule",
            "id": "12345678-0000-0000-0000-000000000001",
            "status": "experimental",
            "description": "A test rule",
            "references": ["http://example.onion"],
            "tags": ["attack.initial_access"],
            "logsource": {"category": "network", "product": "any"},
            "detection": {
                "selection": {"DestinationIp": "1.2.3.4"},
                "condition": "selection",
            },
            "falsepositives": ["Unknown"],
            "level": "medium",
        }

    def test_yaml_output_is_valid_string(self):
        from export.sigma import sigma_rule_to_yaml
        rule = self._sample_rule()
        result = sigma_rule_to_yaml(rule)
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_yaml_parses_back_to_dict(self):
        from export.sigma import sigma_rule_to_yaml
        rule = self._sample_rule()
        yaml_str = sigma_rule_to_yaml(rule)
        parsed = yaml.safe_load(yaml_str)
        self.assertEqual(parsed["title"], rule["title"])
        self.assertEqual(parsed["status"], "experimental")

    def test_yaml_preserves_detection(self):
        from export.sigma import sigma_rule_to_yaml
        rule = self._sample_rule()
        yaml_str = sigma_rule_to_yaml(rule)
        parsed = yaml.safe_load(yaml_str)
        self.assertIn("selection", parsed["detection"])
        self.assertEqual(parsed["detection"]["condition"], "selection")

    def test_yaml_preserves_tags_list(self):
        from export.sigma import sigma_rule_to_yaml
        rule = self._sample_rule()
        rule["tags"] = ["attack.t1071", "attack.c2"]
        yaml_str = sigma_rule_to_yaml(rule)
        parsed = yaml.safe_load(yaml_str)
        self.assertIn("attack.t1071", parsed["tags"])


if __name__ == "__main__":
    unittest.main()
