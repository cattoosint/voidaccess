"""
tests/test_extractor.py — Comprehensive tests for the Phase 2 extractor module.

Test classes
------------
TestRegexPatterns         — extractor/regex_patterns.py
TestNER                   — extractor/ner.py
TestLLMExtract            — extractor/llm_extract.py
TestNormalizer            — extractor/normalizer.py
TestPipeline              — extractor/pipeline.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import types
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Ensure the project root is on sys.path regardless of how pytest is invoked
# ---------------------------------------------------------------------------
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


# ===========================================================================
# TestRegexPatterns
# ===========================================================================


class TestRegexPatterns(unittest.TestCase):
    """Tests for extractor/regex_patterns.py"""

    def setUp(self):
        from extractor import regex_patterns as rp
        self.rp = rp

    # --- Bitcoin ---

    def test_bitcoin_bech32_valid(self):
        text = "Send to bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh and bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"
        result = self.rp.extract_type(text, self.rp.BITCOIN_ADDRESS)
        self.assertIn("bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh", result)
        self.assertIn("bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4", result)

    def test_bitcoin_p2pkh_valid(self):
        text = "Legacy address: 1A1zP1eP5QGefi2DMPTfTL5SLmv7Divf Na 17NdbrSGoUotzeGCcMMCqnFkEvLymoou9j"
        result = self.rp.extract_type(text, self.rp.BITCOIN_ADDRESS)
        self.assertIn("1A1zP1eP5QGefi2DMPTfTL5SLmv7Divf", result)
        self.assertIn("17NdbrSGoUotzeGCcMMCqnFkEvLymoou9j", result)

    def test_bitcoin_p2sh_valid(self):
        text = "P2SH: 3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy and 3FZbgi29cpjq2GjdwV8eyHuJJnkLtktZc5"
        result = self.rp.extract_type(text, self.rp.BITCOIN_ADDRESS)
        self.assertIn("3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy", result)

    def test_bitcoin_non_match(self):
        # Too short, invalid chars
        text = "not-a-wallet xyzABC123 1tooshort 3alsobad"
        result = self.rp.extract_type(text, self.rp.BITCOIN_ADDRESS)
        self.assertEqual(result, [])

    def test_bitcoin_no_partial_match(self):
        # Valid address embedded in longer string — boundary should reject it
        text = "prefix1A1zP1eP5QGefi2DMPTfTL5SLmv7Divfsuffix"
        result = self.rp.extract_type(text, self.rp.BITCOIN_ADDRESS)
        self.assertEqual(result, [])

    # --- Ethereum ---

    def test_ethereum_valid(self):
        # Exactly 40 hex chars after 0x
        text = "ETH: 0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        result = self.rp.extract_type(text, self.rp.ETHEREUM_ADDRESS)
        self.assertIn("0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", result)

    def test_ethereum_valid_second(self):
        text = "Also 0xAbCdEf0123456789AbCdEf0123456789AbCdEf01"
        result = self.rp.extract_type(text, self.rp.ETHEREUM_ADDRESS)
        self.assertIn("0xAbCdEf0123456789AbCdEf0123456789AbCdEf01", result)

    def test_ethereum_word_boundary_longer_hex(self):
        # 41 hex chars after 0x — must NOT match because word boundary fails
        # after 40 chars when the 41st is still a word char
        text = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaF"
        result = self.rp.extract_type(text, self.rp.ETHEREUM_ADDRESS)
        self.assertEqual(result, [])

    def test_ethereum_non_match(self):
        text = "0xGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGG"
        result = self.rp.extract_type(text, self.rp.ETHEREUM_ADDRESS)
        self.assertEqual(result, [])

    # --- Monero ---

    def test_monero_valid(self):
        addr = "4AdUndXHHZ9pfQj27iDAW5RsBSXSzsDFDSDXhMs4RDQXW8qDqN7kNDMugBGhJTaHrEnPjFiUZMBPqXZ3r7EhkLhMhFjgKzd"
        text = f"XMR: {addr}"
        result = self.rp.extract_type(text, self.rp.MONERO_ADDRESS)
        self.assertIn(addr, result)

    def test_monero_too_short(self):
        # 94 chars total (one short)
        addr = "4AdUndXHHZ9pfQj27iDAW5RsBSXSzsDFDSDXhMs4RDQXW8qDqN7kNDMugBGhJTaHrEnPjFiUZMBPqXZ3r7EhkLhMhFjgKz"
        result = self.rp.extract_type(addr, self.rp.MONERO_ADDRESS)
        self.assertEqual(result, [])

    def test_monero_wrong_prefix(self):
        addr = "5AdUndXHHZ9pfQj27iDAW5RsBSXSzsDFDSDXhMs4RDQXW8qDqN7kNDMugBGhJTaHrEnPjFiUZMBPqXZ3r7EhkLhMhFjgKzd"
        result = self.rp.extract_type(addr, self.rp.MONERO_ADDRESS)
        self.assertEqual(result, [])

    # --- Onion URL ---

    def test_onion_full_url_v3(self):
        url = "http://duckduckgogg42xjoc72x3sjasowoarfbgcmvfimaftt6twagswzczad.onion/path?q=1"
        result = self.rp.extract_type(url, self.rp.ONION_URL)
        self.assertTrue(any("onion" in r for r in result))

    def test_onion_bare_hostname_v2(self):
        text = "visit expyuzz4wqqyqhjn.onion for more"
        result = self.rp.extract_type(text, self.rp.ONION_URL)
        self.assertTrue(any("expyuzz4wqqyqhjn.onion" in r for r in result))

    def test_onion_https(self):
        text = "https://facebookwkhpilnemxj7asber7cybh6a5yfv2jhadkmbnow3a5xpq.onion/"
        result = self.rp.extract_type(text, self.rp.ONION_URL)
        self.assertEqual(len(result), 1)

    def test_onion_non_match(self):
        text = "visit example.com instead"
        result = self.rp.extract_type(text, self.rp.ONION_URL)
        self.assertEqual(result, [])

    # --- Email ---

    def test_email_valid(self):
        text = "Contact us at user@example.com or admin@darkforum.org"
        result = self.rp.extract_type(text, self.rp.EMAIL_ADDRESS)
        self.assertIn("user@example.com", result)
        self.assertIn("admin@darkforum.org", result)

    def test_email_valid_second(self):
        text = "reach threat.actor@protonmail.com"
        result = self.rp.extract_type(text, self.rp.EMAIL_ADDRESS)
        self.assertIn("threat.actor@protonmail.com", result)

    def test_email_consecutive_dots_rejected(self):
        text = "bad..dots@example.com"
        result = self.rp.extract_type(text, self.rp.EMAIL_ADDRESS)
        self.assertEqual(result, [])

    def test_email_trailing_dot_rejected(self):
        # local part ends with a dot — _is_valid_email() filters it out
        text = "invalid trailing.@example.com address"
        result = self.rp.extract_type(text, self.rp.EMAIL_ADDRESS)
        self.assertEqual(result, [])

    # --- PGP ---

    def test_pgp_full_block(self):
        text = (
            "-----BEGIN PGP PUBLIC KEY BLOCK-----\n"
            "mQINBF...\n"
            "-----END PGP PUBLIC KEY BLOCK-----"
        )
        result = self.rp.extract_type(text, self.rp.PGP_KEY_BLOCK)
        self.assertEqual(len(result), 1)
        self.assertIn("BEGIN PGP PUBLIC KEY BLOCK", result[0])

    def test_pgp_fingerprint(self):
        text = "Key fingerprint: ABCD 1234 ABCD 1234 ABCD 1234 ABCD 1234 ABCD 1234"
        result = self.rp.extract_type(text, self.rp.PGP_KEY_BLOCK)
        self.assertEqual(len(result), 1)

    def test_pgp_fingerprint_no_spaces_context_required(self):
        text = "Key: ABCD1234ABCD1234ABCD1234ABCD1234ABCD1234"
        result = self.rp.extract_type(text, self.rp.PGP_KEY_BLOCK)
        self.assertEqual(result, [], "Bare 40-char hex without fingerprint context should NOT match")

    def test_pgp_fingerprint_with_space_context(self):
        text = "Key fingerprint ABCD1234ABCD1234ABCD1234ABCD1234ABCD1234"
        result = self.rp.extract_type(text, self.rp.PGP_KEY_BLOCK)
        self.assertEqual(len(result), 1)

    def test_pgp_non_match(self):
        text = "no pgp here just text"
        result = self.rp.extract_type(text, self.rp.PGP_KEY_BLOCK)
        self.assertEqual(result, [])

    def test_pgp_does_not_match_sha1_hash(self):
        sha1_hash = "da39a3ee5e6b4b0d3255bfef95601890afd80709"
        text = f"SHA1: {sha1_hash}"
        pgp_result = self.rp.extract_type(text, self.rp.PGP_KEY_BLOCK)
        self.assertEqual(pgp_result, [], "SHA1 hash must not be matched as PGP key block")
        sha1_result = self.rp.extract_type(text, self.rp.FILE_HASH_SHA1)
        self.assertIn(sha1_hash, sha1_result)

    def test_pgp_colon_separated_fingerprint(self):
        text = "AB:CD:EF:01:23:45:67:89:AB:CD:EF:01:23:45:67:89:AB:CD:EF:01"
        result = self.rp.extract_type(text, self.rp.PGP_KEY_BLOCK)
        self.assertEqual(len(result), 1)

    def test_pgp_fingerprint_context_with_spaces(self):
        text = "Key fingerprint ABCD 1234 ABCD 1234 ABCD 1234 ABCD 1234 ABCD 1234"
        result = self.rp.extract_type(text, self.rp.PGP_KEY_BLOCK)
        self.assertEqual(len(result), 1)

    def test_pgp_fingerprint_context_no_spaces(self):
        text = "Key fingerprint ABCD1234ABCD1234ABCD1234ABCD1234ABCD1234"
        result = self.rp.extract_type(text, self.rp.PGP_KEY_BLOCK)
        self.assertEqual(len(result), 1)

    # --- File Hash MD5 ---

    def test_md5_valid(self):
        text = "MD5: d41d8cd98f00b204e9800998ecf8427e"
        result = self.rp.extract_type(text, self.rp.FILE_HASH_MD5)
        self.assertIn("d41d8cd98f00b204e9800998ecf8427e", result)

    def test_md5_uppercase(self):
        text = "md5: D41D8CD98F00B204E9800998ECF8427E"
        result = self.rp.extract_type(text, self.rp.FILE_HASH_MD5)
        self.assertIn("D41D8CD98F00B204E9800998ECF8427E", result)

    def test_md5_32_chars_exact(self):
        text = "hash is abcdef0123456789abcdef0123456789"
        result = self.rp.extract_type(text, self.rp.FILE_HASH_MD5)
        self.assertIn("abcdef0123456789abcdef0123456789", result)

    def test_md5_wrong_length_31(self):
        text = "hash abcdef0123456789abcdef0123456"
        result = self.rp.extract_type(text, self.rp.FILE_HASH_MD5)
        self.assertEqual(result, [])

    def test_md5_wrong_length_33(self):
        text = "hash abcdef0123456789abcdef012345678"
        result = self.rp.extract_type(text, self.rp.FILE_HASH_MD5)
        self.assertEqual(result, [])

    # --- File Hash SHA1 ---

    def test_sha1_valid(self):
        text = "SHA1: da39a3ee5e6b4b0d3255bfef95601890afd80709"
        result = self.rp.extract_type(text, self.rp.FILE_HASH_SHA1)
        self.assertIn("da39a3ee5e6b4b0d3255bfef95601890afd80709", result)

    def test_sha1_uppercase(self):
        text = "sha1: DA39A3EE5E6B4B0D3255BFEF95601890AFD80709"
        result = self.rp.extract_type(text, self.rp.FILE_HASH_SHA1)
        self.assertIn("DA39A3EE5E6B4B0D3255BFEF95601890AFD80709", result)

    def test_sha1_40_chars_exact(self):
        text = "abc123def456789abc123def456789abc123def4"
        result = self.rp.extract_type(text, self.rp.FILE_HASH_SHA1)
        self.assertIn("abc123def456789abc123def456789abc123def4", result)

    def test_sha1_wrong_length_39(self):
        text = "hash abc123def456789abc123def456789abc123de"
        result = self.rp.extract_type(text, self.rp.FILE_HASH_SHA1)
        self.assertEqual(result, [])

    def test_sha1_wrong_length_41(self):
        text = "hash abc123def456789abc123def456789abc123def45"
        result = self.rp.extract_type(text, self.rp.FILE_HASH_SHA1)
        self.assertEqual(result, [])

    def test_sha1_not_matched_by_pgp(self):
        sha1 = "da39a3ee5e6b4b0d3255bfef95601890afd80709"
        text = f"file hash: {sha1}"
        pgp_result = self.rp.extract_type(text, self.rp.PGP_KEY_BLOCK)
        self.assertEqual(pgp_result, [], "SHA1 must not be classified as PGP")

    # --- File Hash SHA256 ---

    def test_sha256_valid(self):
        text = "SHA256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        result = self.rp.extract_type(text, self.rp.FILE_HASH_SHA256)
        self.assertIn("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", result)

    def test_sha256_64_chars_exact(self):
        text = "a3f8b2c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2"
        result = self.rp.extract_type(text, self.rp.FILE_HASH_SHA256)
        self.assertIn("a3f8b2c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2", result)

    def test_sha256_wrong_length_63(self):
        text = "hash a3f8b2c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f"
        result = self.rp.extract_type(text, self.rp.FILE_HASH_SHA256)
        self.assertEqual(result, [])

    def test_sha256_wrong_length_65(self):
        text = "hash a3f8b2c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b"
        result = self.rp.extract_type(text, self.rp.FILE_HASH_SHA256)
        self.assertEqual(result, [])

    # --- MITRE_TECHNIQUE ---

    def test_mitre_valid_base_technique(self):
        text = "T1486 Data Encrypted for Impact"
        result = self.rp.extract_type(text, self.rp.MITRE_TECHNIQUE)
        self.assertIn("T1486", result)

    def test_mitre_valid_sub_technique(self):
        text = "T1071.001 Application Layer Protocol: Web Protocols"
        result = self.rp.extract_type(text, self.rp.MITRE_TECHNIQUE)
        self.assertIn("T1071.001", result)

    def test_mitre_uppercase_normalized(self):
        text = "t1059 command and scripting interpreter"
        result = self.rp.extract_type(text, self.rp.MITRE_TECHNIQUE)
        self.assertIn("T1059", result)

    def test_mitre_4_digits_valid(self):
        text = "T1234 technique"
        result = self.rp.extract_type(text, self.rp.MITRE_TECHNIQUE)
        self.assertIn("T1234", result)

    def test_mitre_multiple(self):
        text = "Attacker used T1486 for encryption and T1059 for execution"
        result = self.rp.extract_type(text, self.rp.MITRE_TECHNIQUE)
        self.assertIn("T1486", result)
        self.assertIn("T1059", result)

    def test_mitre_too_short_3_digits(self):
        text = "T123 is not valid"
        result = self.rp.extract_type(text, self.rp.MITRE_TECHNIQUE)
        self.assertEqual(result, [])

    def test_mitre_leading_letter_rejected(self):
        text = "AT1486 is not valid"
        result = self.rp.extract_type(text, self.rp.MITRE_TECHNIQUE)
        self.assertEqual(result, [])

    def test_mitre_7_digit_id(self):
        text = "CVE-2024-1234567 was used with T1486"
        result = self.rp.extract_type(text, self.rp.MITRE_TECHNIQUE)
        self.assertIn("T1486", result)

    # --- CVE ---

    def test_cve_valid(self):
        text = "Exploiting CVE-2024-12345 and cve-2023-9999999"
        result = self.rp.extract_type(text, self.rp.CVE_NUMBER)
        self.assertIn("CVE-2024-12345", result)
        self.assertIn("CVE-2023-9999999", result)

    def test_cve_uppercase_normalised(self):
        text = "cve-2024-00001"
        result = self.rp.extract_type(text, self.rp.CVE_NUMBER)
        self.assertIn("CVE-2024-00001", result)

    def test_cve_non_match(self):
        text = "CVE-ABCD-1234 CVE-2024-123 not-a-cve"
        result = self.rp.extract_type(text, self.rp.CVE_NUMBER)
        self.assertEqual(result, [])

    def test_cve_non_match_too_short(self):
        text = "CVE-2024-123"
        result = self.rp.extract_type(text, self.rp.CVE_NUMBER)
        self.assertEqual(result, [])

    # --- IP address ---

    def test_ip_public_valid(self):
        text = "C2 server at 185.220.101.1 and 91.108.56.100"
        result = self.rp.extract_type(text, self.rp.IP_ADDRESS)
        self.assertIn("185.220.101.1", result)
        self.assertIn("91.108.56.100", result)

    def test_ip_rfc1918_excluded(self):
        text = "Internal: 10.0.0.1 192.168.1.1 172.16.0.5 172.31.255.255"
        result = self.rp.extract_type(text, self.rp.IP_ADDRESS)
        self.assertEqual(result, [])

    def test_ip_loopback_excluded(self):
        text = "Loopback 127.0.0.1 is filtered"
        result = self.rp.extract_type(text, self.rp.IP_ADDRESS)
        self.assertEqual(result, [])

    def test_ip_non_match(self):
        text = "not an ip 999.999.999.999"
        result = self.rp.extract_type(text, self.rp.IP_ADDRESS)
        self.assertEqual(result, [])

    # --- Phone ---

    def test_phone_e164_valid(self):
        text = "call +14155552671 or +447911123456"
        result = self.rp.extract_type(text, self.rp.PHONE_NUMBER)
        self.assertIn("+14155552671", result)
        self.assertIn("+447911123456", result)

    def test_phone_non_match(self):
        text = "not a phone: 123456"
        result = self.rp.extract_type(text, self.rp.PHONE_NUMBER)
        self.assertEqual(result, [])

    # --- Paste URL ---

    def test_paste_pastebin(self):
        text = "leaked data at https://pastebin.com/abc123XY"
        result = self.rp.extract_type(text, self.rp.PASTE_URL)
        self.assertIn("https://pastebin.com/abc123XY", result)

    def test_paste_rentry(self):
        text = "see https://rentry.co/leak2024"
        result = self.rp.extract_type(text, self.rp.PASTE_URL)
        self.assertIn("https://rentry.co/leak2024", result)

    def test_paste_non_match(self):
        text = "https://github.com/user/repo"
        result = self.rp.extract_type(text, self.rp.PASTE_URL)
        self.assertEqual(result, [])

    # --- extract_all ---

    def test_extract_all_returns_all_keys(self):
        result = self.rp.extract_all("no entities here")
        for key in self.rp.ENTITY_TYPES:
            self.assertIn(key, result)
            self.assertIsInstance(result[key], list)

    def test_extract_all_deduplicates(self):
        # Exactly 40 hex chars after 0x
        addr = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        text = f"{addr} and {addr} appear twice"
        result = self.rp.extract_all(text)
        self.assertEqual(result[self.rp.ETHEREUM_ADDRESS].count(addr), 1)

    def test_extract_all_never_raises(self):
        # Should not raise on None-like input or weird text
        result = self.rp.extract_all("")
        self.assertIsInstance(result, dict)

    # --- extract_type ---

    def test_extract_type_raises_on_unknown(self):
        with self.assertRaises(ValueError):
            self.rp.extract_type("text", "NOT_A_REAL_TYPE")

    def test_extract_type_empty_text(self):
        result = self.rp.extract_type("", self.rp.BITCOIN_ADDRESS)
        self.assertEqual(result, [])


# ===========================================================================
# TestNER
# ===========================================================================


class TestNER(unittest.TestCase):
    """Tests for extractor/ner.py"""

    def setUp(self):
        # Reset the spaCy singleton state so tests can control it
        import extractor.ner as ner_module
        self.ner = ner_module
        # Patch _nlp_attempted so we can control spaCy availability per test
        self._orig_attempted = ner_module._nlp_attempted
        self._orig_nlp = ner_module._nlp

    def tearDown(self):
        self.ner._nlp_attempted = self._orig_attempted
        self.ner._nlp = self._orig_nlp

    # --- Malware dictionary ---

    def test_malware_dictionary_loads(self):
        malware_set = self.ner.load_malware_dictionary()
        self.assertIsInstance(malware_set, set)
        self.assertGreaterEqual(len(malware_set), 200)

    def test_malware_dictionary_contains_known_families(self):
        malware_set = self.ner.load_malware_dictionary()
        for name in ["LockBit", "REvil", "Emotet", "Conti", "TrickBot"]:
            self.assertIn(name, malware_set)

    def test_malware_matching_case_insensitive(self):
        text = "The lockbit group posted a new leak. REVIL is back."
        result = self.ner.extract_named_entities(text)
        malware = [m.lower() for m in result[self.ner.MALWARE_FAMILY]]
        self.assertIn("lockbit", malware)
        self.assertIn("revil", malware)

    def test_malware_word_bounded(self):
        # "lockbitx" should not match "LockBit"
        text = "using lockbitxtra software"
        result = self.ner.extract_named_entities(text)
        # Should not have a match for LockBit here (word boundary enforced)
        malware = [m.lower() for m in result[self.ner.MALWARE_FAMILY]]
        self.assertNotIn("lockbit", malware)

    def test_ransomware_group_subset(self):
        text = "BlackCat ransomware group claimed the attack"
        result = self.ner.extract_named_entities(text)
        rw = [r.lower() for r in result[self.ner.RANSOMWARE_GROUP]]
        self.assertIn("blackcat", rw)

    # --- Missing spaCy model ---

    def test_missing_spacy_returns_empty_dict_without_raising(self):
        # Simulate spaCy not being installed by making _get_nlp return None
        self.ner._nlp_attempted = True
        self.ner._nlp = None

        # Should still return the correct structure without raising
        result = self.ner.extract_named_entities("LockBit ransomware attacked IBM")
        self.assertIsInstance(result, dict)
        self.assertIn(self.ner.MALWARE_FAMILY, result)
        self.assertIn(self.ner.THREAT_ACTOR_HANDLE, result)

    # --- Threat actor handles ---

    def test_threat_actor_handle_extracted(self):
        text = "posted by darkking99 on the forum"
        result = self.ner.extract_named_entities(text)
        handles = result[self.ner.THREAT_ACTOR_HANDLE]
        self.assertIn("darkking99", handles)

    def test_threat_actor_handle_alias(self):
        text = "known as ShadowBroker on multiple forums"
        result = self.ner.extract_named_entities(text)
        handles = result[self.ner.THREAT_ACTOR_HANDLE]
        self.assertIn("ShadowBroker", handles)

    # --- extract_named_entities structure ---

    def test_extract_named_entities_returns_correct_keys(self):
        result = self.ner.extract_named_entities("test text")
        for key in [
            self.ner.THREAT_ACTOR_HANDLE,
            self.ner.MALWARE_FAMILY,
            self.ner.RANSOMWARE_GROUP,
            self.ner.ORGANIZATION_NAME,
        ]:
            self.assertIn(key, result)
            self.assertIsInstance(result[key], list)

    def test_extract_named_entities_never_raises(self):
        result = self.ner.extract_named_entities("")
        self.assertIsInstance(result, dict)


# ===========================================================================
# TestLLMExtract
# ===========================================================================


class TestLLMExtract(unittest.TestCase):
    """Tests for extractor/llm_extract.py"""

    def _run(self, coro):
        return asyncio.run(coro)

    def setUp(self):
        from extractor import llm_extract
        self.llm_extract = llm_extract

    def _make_llm(self, response_json: dict) -> MagicMock:
        """Return a mock LLM that responds with *response_json* as JSON."""
        llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = json.dumps(response_json)
        llm.ainvoke = AsyncMock(return_value=mock_response)
        return llm

    # --- None llm ---

    def test_none_llm_returns_existing_unchanged(self):
        existing = {"BITCOIN_ADDRESS": ["bc1qtest"], "CVE_NUMBER": []}
        result = self._run(
            self.llm_extract.extract_with_llm("text with bc1qtest", None, existing)
        )
        self.assertEqual(result, existing)

    # --- Valid JSON response ---

    def test_valid_json_parsed_and_merged(self):
        existing = {"BITCOIN_ADDRESS": ["bc1qtest"]}
        llm = self._make_llm({
            "crypto_wallets": ["bc1qnewaddress"],
            "threat_actor_handles": ["hackerx"],
            "malware_names": ["Emotet"],
            "dates": ["2024-03-15"],
            "urls": ["http://example.onion"],
        })
        result = self._run(
            self.llm_extract.extract_with_llm("text with bc1qtest", llm, existing)
        )
        self.assertIn("bc1qtest", result.get("BITCOIN_ADDRESS", []))
        self.assertIn("bc1qnewaddress", result.get("BITCOIN_ADDRESS", []))
        self.assertIn("hackerx", result.get("THREAT_ACTOR_HANDLE", []))
        self.assertIn("Emotet", result.get("MALWARE_FAMILY", []))

    # --- Invalid JSON response ---

    def test_invalid_json_logs_error_returns_existing(self):
        existing = {"BITCOIN_ADDRESS": ["bc1qtest"]}
        llm = MagicMock()
        bad_response = MagicMock()
        bad_response.content = "this is not json at all!!!"
        llm.ainvoke = AsyncMock(return_value=bad_response)

        import logging
        with self.assertLogs("extractor.llm_extract", level="WARNING"):
            result = self._run(
                self.llm_extract.extract_with_llm("text with bc1qtest", llm, existing)
            )
        # Result should contain the existing entities at minimum
        self.assertIn("bc1qtest", result.get("BITCOIN_ADDRESS", []))

    # --- No existing entities (skip LLM) ---

    def test_no_existing_entities_skips_llm(self):
        existing = {"BITCOIN_ADDRESS": [], "CVE_NUMBER": []}
        llm = MagicMock()
        llm.ainvoke = AsyncMock()
        result = self._run(
            self.llm_extract.extract_with_llm("some text", llm, existing)
        )
        llm.ainvoke.assert_not_called()
        self.assertEqual(result, existing)

    # --- Chunking ---

    def test_text_chunked_at_max_chunk_chars(self):
        text = "A" * 5000
        # Add an entity to existing so LLM is triggered
        existing = {"BITCOIN_ADDRESS": ["bc1qtest"]}
        llm = self._make_llm({
            "crypto_wallets": [],
            "threat_actor_handles": [],
            "malware_names": [],
            "dates": [],
            "urls": [],
        })
        self._run(
            self.llm_extract.extract_with_llm(text, llm, existing, max_chunk_chars=2000)
        )
        # With 5000 chars and 2000 chunk size + 200 overlap, expect multiple calls
        self.assertGreater(llm.ainvoke.call_count, 1)

    def test_single_chunk_for_short_text(self):
        text = "short text"
        existing = {"CVE_NUMBER": ["CVE-2024-1234"]}
        llm = self._make_llm({
            "crypto_wallets": [],
            "threat_actor_handles": [],
            "malware_names": [],
            "dates": [],
            "urls": [],
        })
        self._run(
            self.llm_extract.extract_with_llm(text, llm, existing, max_chunk_chars=4000)
        )
        self.assertEqual(llm.ainvoke.call_count, 1)

    def test_deduplication_across_chunks(self):
        # LLM returns the same value in two different chunk responses
        existing = {"BITCOIN_ADDRESS": ["bc1qexisting"]}
        call_count = [0]
        async def _fake_invoke(prompt):
            call_count[0] += 1
            resp = MagicMock()
            resp.content = json.dumps({
                "crypto_wallets": ["bc1qduplicated"],
                "threat_actor_handles": [],
                "malware_names": [],
                "dates": [],
                "urls": [],
            })
            return resp

        llm = MagicMock()
        llm.ainvoke = _fake_invoke
        result = self._run(
            self.llm_extract.extract_with_llm("A" * 3000, llm, existing, max_chunk_chars=2000)
        )
        self.assertEqual(result["BITCOIN_ADDRESS"].count("bc1qduplicated"), 1)

    def test_chunk_text_overlap(self):
        chunks = self.llm_extract._chunk_text("X" * 1000, max_chars=400, overlap=100)
        self.assertGreater(len(chunks), 1)
        # Verify overlap: end of chunk N overlaps with start of chunk N+1
        for i in range(len(chunks) - 1):
            self.assertEqual(chunks[i][-100:], chunks[i + 1][:100])


# ===========================================================================
# TestNormalizer
# ===========================================================================


class TestNormalizer(unittest.TestCase):
    """Tests for extractor/normalizer.py"""

    def setUp(self):
        from extractor import normalizer
        self.norm = normalizer

    def test_cve_normalised_to_uppercase(self):
        raw = {"CVE_NUMBER": ["cve-2024-12345"]}
        result = self.norm.normalize_entities(raw, "http://example.onion")
        values = [e.value for e in result]
        self.assertIn("CVE-2024-12345", values)

    def test_email_normalised_to_lowercase(self):
        raw = {"EMAIL_ADDRESS": ["User@Example.COM"]}
        result = self.norm.normalize_entities(raw, "http://example.onion")
        values = [e.value for e in result]
        self.assertIn("user@example.com", values)

    def test_bitcoin_bech32_lowercased(self):
        raw = {"BITCOIN_ADDRESS": ["BC1QTEST123456789012345678901234567890"]}
        result = self.norm.normalize_entities(raw, "http://example.onion")
        values = [e.value for e in result]
        self.assertTrue(any(v.startswith("bc1") for v in values))

    def test_bitcoin_legacy_unchanged(self):
        addr = "1A1zP1eP5QGefi2DMPTfTL5SLmv7Divf"
        raw = {"BITCOIN_ADDRESS": [addr]}
        result = self.norm.normalize_entities(raw, "http://example.onion")
        values = [e.value for e in result]
        self.assertIn(addr, values)

    def test_onion_url_normalised_via_crawler_utils(self):
        # normalize_url from crawler.utils lowercases and strips trailing slash
        raw = {"ONION_URL": ["HTTP://EXAMPLE.ONION/"]}
        result = self.norm.normalize_entities(raw, "http://source.onion")
        values = [e.value for e in result]
        # Should be lowercase, trailing slash stripped
        self.assertTrue(any("http://example.onion" in v.lower() for v in values))

    def test_duplicate_values_deduplicated(self):
        raw = {"CVE_NUMBER": ["CVE-2024-12345", "cve-2024-12345", "CVE-2024-12345"]}
        result = self.norm.normalize_entities(raw, "http://example.onion")
        cve_values = [e.value for e in result if e.entity_type == "CVE_NUMBER"]
        self.assertEqual(len(cve_values), 1)

    def test_normalized_entity_has_correct_fields(self):
        raw = {"EMAIL_ADDRESS": ["test@example.com"]}
        import uuid

        pid = uuid.uuid4()
        result = self.norm.normalize_entities(raw, "http://page.onion", page_id=pid)
        self.assertEqual(len(result), 1)
        ent = result[0]
        self.assertEqual(ent.entity_type, "EMAIL_ADDRESS")
        self.assertEqual(ent.value, "test@example.com")
        self.assertEqual(ent.confidence, 1.0)  # regex type
        self.assertEqual(ent.source_url, "http://page.onion")
        self.assertEqual(ent.page_id, pid)
        self.assertIsInstance(ent.context_snippet, str)

    def test_ner_type_has_lower_confidence(self):
        raw = {"MALWARE_FAMILY": ["LockBit"]}
        result = self.norm.normalize_entities(raw, "http://example.onion")
        self.assertEqual(result[0].confidence, 0.85)

    def test_llm_type_has_lowest_confidence(self):
        raw = {"DATE": ["2024-03-15"]}
        result = self.norm.normalize_entities(raw, "http://example.onion")
        self.assertEqual(result[0].confidence, 0.75)

    def test_merge_with_db_returns_empty_without_database_url(self):
        # Ensure DATABASE_URL is not set
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("DATABASE_URL", None)
            entities = [
                self.norm.NormalizedEntity(
                    entity_type="CVE_NUMBER",
                    value="CVE-2024-12345",
                    confidence=1.0,
                    source_url="http://example.onion",
                    page_id=None,
                    context_snippet="",
                )
            ]
            result = self.norm.merge_with_db(entities)
            self.assertEqual(result, [])

    def test_merge_with_db_empty_entity_list(self):
        result = self.norm.merge_with_db([])
        self.assertEqual(result, [])

    def test_normalize_entities_empty_values_skipped(self):
        raw = {"CVE_NUMBER": ["", "  ", "CVE-2024-9999"]}
        result = self.norm.normalize_entities(raw, "http://example.onion")
        values = [e.value for e in result]
        self.assertNotIn("", values)
        self.assertIn("CVE-2024-9999", values)

    def test_blocklist_filters_leet_generic(self):
        """h4ck3r and variants should be filtered"""
        from extractor.normalizer import is_blocked_entity
        assert is_blocked_entity("THREAT_ACTOR_HANDLE", "h4ck3r") is True
        assert is_blocked_entity("THREAT_ACTOR_HANDLE", "h4ck") is True

    def test_blocklist_keeps_specific_handles(self):
        """Numbered specific handles should NOT be filtered"""
        from extractor.normalizer import is_blocked_entity
        assert is_blocked_entity("THREAT_ACTOR_HANDLE", "forfun3") is False
        assert is_blocked_entity("THREAT_ACTOR_HANDLE", "hey_pussy3") is False
        assert is_blocked_entity("THREAT_ACTOR_HANDLE", "OmenOrca") is False
        assert is_blocked_entity("THREAT_ACTOR_HANDLE", "weja") is False

    def test_blocklist_filters_tool_names(self):
        """Known tool names should be filtered as THREAT_ACTOR"""
        from extractor.normalizer import is_blocked_entity
        assert is_blocked_entity("THREAT_ACTOR_HANDLE", "vproxy") is True
        assert is_blocked_entity("THREAT_ACTOR_HANDLE", "nmap") is True

    def test_blocklist_keeps_tool_names_for_malware_type(self):
        """Tool names are valid MALWARE entities even if not valid THREAT_ACTOR"""
        from extractor.normalizer import is_blocked_entity
        assert is_blocked_entity("MALWARE_FAMILY", "cobaltstrike") is False

    # --- Hash length validation ---

    def test_hash_md5_invalid_length_rejected(self):
        from extractor.normalizer import _validate_hash_length
        assert _validate_hash_length("FILE_HASH_MD5", "abc123") is False
        assert _validate_hash_length("FILE_HASH_MD5", "d41d8cd98f00b204e9800998ecf8427e") is True

    def test_hash_sha1_invalid_length_rejected(self):
        from extractor.normalizer import _validate_hash_length
        assert _validate_hash_length("FILE_HASH_SHA1", "abc123") is False
        assert _validate_hash_length("FILE_HASH_SHA1", "da39a3ee5e6b4b0d3255bfef95601890afd80709") is True

    def test_hash_sha256_invalid_length_rejected(self):
        from extractor.normalizer import _validate_hash_length
        assert _validate_hash_length("FILE_HASH_SHA256", "abc123") is False
        assert _validate_hash_length("FILE_HASH_SHA256", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855") is True

    # --- Type conflict resolution ---

    def test_resolve_conflicts_keeps_highest_priority(self):
        from extractor.normalizer import resolve_entity_type_conflicts, NormalizedEntity
        entities = [
            NormalizedEntity(
                entity_type="MALWARE_FAMILY",
                value="Sodinokibi",
                confidence=0.85,
                source_url="http://test.onion",
                page_id=None,
            ),
            NormalizedEntity(
                entity_type="ORGANIZATION_NAME",
                value="Sodinokibi",
                confidence=0.75,
                source_url="http://test.onion",
                page_id=None,
            ),
        ]
        resolved = resolve_entity_type_conflicts(entities)
        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0].entity_type, "MALWARE_FAMILY")

    def test_resolve_conflicts_equal_priority_tiebreak(self):
        from extractor.normalizer import resolve_entity_type_conflicts, NormalizedEntity
        entities = [
            NormalizedEntity(
                entity_type="RANSOMWARE_GROUP",
                value="Sodinokibi",
                confidence=0.85,
                source_url="http://test.onion",
                page_id=None,
            ),
            NormalizedEntity(
                entity_type="THREAT_ACTOR",
                value="Sodinokibi",
                confidence=0.85,
                source_url="http://test.onion",
                page_id=None,
            ),
            NormalizedEntity(
                entity_type="MALWARE_FAMILY",
                value="Sodinokibi",
                confidence=0.85,
                source_url="http://test.onion",
                page_id=None,
            ),
        ]
        resolved = resolve_entity_type_conflicts(entities)
        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0].entity_type, "RANSOMWARE_GROUP")

    def test_resolve_conflicts_no_conflict_unchanged(self):
        from extractor.normalizer import resolve_entity_type_conflicts, NormalizedEntity
        entities = [
            NormalizedEntity(
                entity_type="CVE_NUMBER",
                value="CVE-2025-31324",
                confidence=1.0,
                source_url="http://test.onion",
                page_id=None,
            ),
        ]
        resolved = resolve_entity_type_conflicts(entities)
        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0].entity_type, "CVE_NUMBER")

    def test_resolve_conflicts_multiple_values(self):
        from extractor.normalizer import resolve_entity_type_conflicts, NormalizedEntity
        entities = [
            NormalizedEntity(
                entity_type="CVE_NUMBER",
                value="CVE-2025-31324",
                confidence=1.0,
                source_url="http://test.onion",
                page_id=None,
            ),
            NormalizedEntity(
                entity_type="MALWARE_FAMILY",
                value="LockBit",
                confidence=0.85,
                source_url="http://test.onion",
                page_id=None,
            ),
            NormalizedEntity(
                entity_type="ORGANIZATION_NAME",
                value="LockBit",
                confidence=0.75,
                source_url="http://test.onion",
                page_id=None,
            ),
        ]
        resolved = resolve_entity_type_conflicts(entities)
        self.assertEqual(len(resolved), 2)
        types = {e.entity_type for e in resolved}
        self.assertIn("CVE_NUMBER", types)
        self.assertIn("MALWARE_FAMILY", types)

    def test_resolve_conflicts_logs_debug(self):
        import logging
        from extractor.normalizer import resolve_entity_type_conflicts, NormalizedEntity
        entities = [
            NormalizedEntity(
                entity_type="MALWARE_FAMILY",
                value="Revil",
                confidence=0.85,
                source_url="http://test.onion",
                page_id=None,
            ),
            NormalizedEntity(
                entity_type="ORGANIZATION_NAME",
                value="Revil",
                confidence=0.75,
                source_url="http://test.onion",
                page_id=None,
            ),
        ]
        with self.assertLogs("extractor.normalizer", level="DEBUG") as cm:
            resolve_entity_type_conflicts(entities)
        self.assertTrue(any("Type conflict" in log for log in cm.output))



# ===========================================================================
# TestPipeline
# ===========================================================================


class TestPipeline(unittest.TestCase):
    """Tests for extractor/pipeline.py"""

    def _run(self, coro):
        return asyncio.run(coro)

    def setUp(self):
        from extractor import pipeline
        self.pipeline = pipeline

    def _page_with_entity(self) -> str:
        """Return page text that contains at least one regex-matchable entity."""
        return (
            "The attacker used wallet bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh "
            "to collect ransom. CVE-2024-12345 was exploited. "
            "Contact: evil@darkmail.onion"
        )

    # --- Full pipeline ---

    def test_full_pipeline_runs_and_returns_result(self):
        text = self._page_with_entity()
        result = self._run(
            self.pipeline.extract_entities_from_page(
                page_text=text,
                page_url="http://example.onion",
            )
        )
        self.assertIsInstance(result, self.pipeline.ExtractionResult)
        self.assertGreater(result.entity_count, 0)
        self.assertEqual(result.page_url, "http://example.onion")

    def test_pipeline_counts_by_type(self):
        text = "CVE-2024-00001 and CVE-2024-00002"
        result = self._run(
            self.pipeline.extract_entities_from_page(
                page_text=text,
                page_url="http://example.onion",
            )
        )
        self.assertIn("CVE_NUMBER", result.entities_by_type)
        self.assertGreaterEqual(result.entities_by_type["CVE_NUMBER"], 2)

    def test_pipeline_entity_ids_empty_without_db(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("DATABASE_URL", None)
            text = self._page_with_entity()
            result = self._run(
                self.pipeline.extract_entities_from_page(
                    page_text=text,
                    page_url="http://example.onion",
                )
            )
            self.assertEqual(result.entity_ids, [])

    # --- LLM extraction toggle ---

    def test_llm_skipped_when_run_llm_extraction_false(self):
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock()
        text = self._page_with_entity()
        self._run(
            self.pipeline.extract_entities_from_page(
                page_text=text,
                page_url="http://example.onion",
                llm=mock_llm,
                run_llm_extraction=False,
            )
        )
        mock_llm.ainvoke.assert_not_called()

    def test_llm_called_when_run_llm_extraction_true(self):
        resp = MagicMock()
        resp.content = json.dumps({
            "crypto_wallets": [],
            "threat_actor_handles": [],
            "malware_names": [],
            "dates": [],
            "urls": [],
        })
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=resp)

        text = self._page_with_entity()
        self._run(
            self.pipeline.extract_entities_from_page(
                page_text=text,
                page_url="http://example.onion",
                llm=mock_llm,
                run_llm_extraction=True,
            )
        )
        mock_llm.ainvoke.assert_called()

    # --- extract_entities_from_pages ---

    def test_multiple_pages_all_processed(self):
        pages = [
            {"url": f"http://page{i}.onion", "text": f"CVE-2024-{10000 + i}"}
            for i in range(3)
        ]
        results = self._run(
            self.pipeline.extract_entities_from_pages(pages)
        )
        self.assertEqual(len(results), 3)

    def test_one_page_failure_does_not_block_others(self):
        """Simulate one page raising inside extract_entities_from_page."""
        pages = [
            {"url": "http://good.onion", "text": "CVE-2024-11111"},
            {"url": "http://bad.onion", "text": "good text"},
        ]

        original_fn = self.pipeline.extract_entities_from_page

        async def _patched(page_text, page_url, **kwargs):
            if "bad.onion" in page_url:
                raise RuntimeError("simulated failure")
            return await original_fn(page_text=page_text, page_url=page_url, **kwargs)

        with patch.object(self.pipeline, "extract_entities_from_page", _patched):
            results = self._run(
                self.pipeline.extract_entities_from_pages(pages)
            )

        self.assertEqual(len(results), 2)
        urls = [r.page_url for r in results]
        self.assertIn("http://good.onion", urls)
        bad = next(r for r in results if "bad.onion" in r.page_url)
        self.assertGreater(len(bad.errors), 0)

    def test_max_concurrent_semaphore_respected(self):
        """Verify concurrency doesn't exceed max_concurrent."""
        active = [0]
        peak = [0]

        original_fn = self.pipeline.extract_entities_from_page

        async def _counted(page_text, page_url, **kwargs):
            active[0] += 1
            peak[0] = max(peak[0], active[0])
            result = await original_fn(
                page_text=page_text, page_url=page_url, **kwargs
            )
            active[0] -= 1
            return result

        pages = [
            {"url": f"http://p{i}.onion", "text": f"CVE-2024-{20000 + i}"}
            for i in range(6)
        ]

        with patch.object(self.pipeline, "extract_entities_from_page", _counted):
            self._run(
                self.pipeline.extract_entities_from_pages(pages, max_concurrent=3)
            )

        self.assertLessEqual(peak[0], 3)

    def test_extraction_result_dataclass_fields(self):
        pages = [{"url": "http://test.onion", "text": "no entities here"}]
        results = self._run(self.pipeline.extract_entities_from_pages(pages))
        r = results[0]
        self.assertEqual(r.page_url, "http://test.onion")
        self.assertIsInstance(r.entity_count, int)
        self.assertIsInstance(r.entities_by_type, dict)
        self.assertIsInstance(r.entity_ids, list)
        self.assertIsInstance(r.errors, list)


# ===========================================================================
# TestExtractorInit
# ===========================================================================


class TestExtractorInit(unittest.TestCase):
    """Verify the public exports from extractor/__init__.py"""

    def test_exports_exist(self):
        from extractor import (
            ExtractionResult,
            extract_entities_from_page,
            extract_entities_from_pages,
        )
        self.assertTrue(callable(extract_entities_from_page))
        self.assertTrue(callable(extract_entities_from_pages))
        # ExtractionResult should be instantiable
        r = ExtractionResult(page_url="x", entity_count=0)
        self.assertEqual(r.page_url, "x")


# ===========================================================================
# Entry point
# ===========================================================================

if __name__ == "__main__":
    unittest.main()
