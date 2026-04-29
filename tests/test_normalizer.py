"""Tests for extractor/normalizer.py"""

import sys
import unittest
from unittest.mock import patch, MagicMock


class TestEthChecksum(unittest.TestCase):
    """Test ETH address normalization."""

    def _get_mock_web3_module(self):
        mock_web3 = MagicMock()
        mock_web3.Web3.to_checksum_address = lambda addr: addr
        return mock_web3

    def test_valid_eth_address_with_web3(self):
        """Valid ETH address returns checksummed version when web3 is available."""
        mock_web3 = self._get_mock_web3_module()

        with patch.dict(sys.modules, {"web3": mock_web3}):
            import extractor.normalizer as normalizer_module
            import importlib
            importlib.reload(normalizer_module)

            normalizer_module.WEB3_AVAILABLE = True
            result = normalizer_module._eth_checksum("0x742d35cc6634c0532925a3b844bc9e7595f0eb1e")
            self.assertEqual(result, "0x742d35cc6634c0532925a3b844bc9e7595f0eb1e")

    def test_valid_eth_address_lowercase_returns_checksummed(self):
        """Valid lowercase ETH address returns checksummed version."""
        mock_web3 = self._get_mock_web3_module()

        with patch.dict(sys.modules, {"web3": mock_web3}):
            import extractor.normalizer as normalizer_module
            import importlib
            importlib.reload(normalizer_module)

            normalizer_module.WEB3_AVAILABLE = True
            result = normalizer_module._eth_checksum("0x742d35cc6634c0532925a3b844bc9e7595f0eb1e")
            self.assertEqual(result, "0x742d35cc6634c0532925a3b844bc9e7595f0eb1e")

    def test_valid_eth_address_without_web3(self):
        """Valid ETH address returns lowercase when web3 is not available."""
        import extractor.normalizer as normalizer_module

        normalizer_module.WEB3_AVAILABLE = False
        addr = "0x742d35Cc6634C0532925a3b844Bc9e7595f0eB1E"
        result = normalizer_module._eth_checksum(addr)
        self.assertEqual(result, "0x742d35cc6634c0532925a3b844bc9e7595f0eb1e")

    def test_invalid_eth_address_returns_lowercase(self):
        """Invalid ETH address does not raise, returns lowercased input."""
        import extractor.normalizer as normalizer_module

        normalizer_module.WEB3_AVAILABLE = True
        invalid_addrs = [
            "0x742d35Cc6634C0532925a3b844Bc9e7595f0eB1",  # too short
            "0x742d35Cc6634C0532925a3b844Bc9e7595f0eB1EE",  # too long
            "742d35Cc6634C0532925a3b844Bc9e7595f0eB1E",  # missing 0x
            "not an address",
            "",
        ]

        for addr in invalid_addrs:
            with self.subTest(addr=addr):
                result = normalizer_module._eth_checksum(addr)
                self.assertEqual(result, addr.lower())

    def test_checksum_failure_returns_lowercase(self):
        """Web3 checksum failure is handled gracefully."""
        mock_web3 = MagicMock()
        mock_web3.Web3.to_checksum_address.side_effect = ValueError("Invalid address")

        with patch.dict(sys.modules, {"web3": mock_web3}):
            import extractor.normalizer as normalizer_module
            import importlib
            importlib.reload(normalizer_module)

            normalizer_module.WEB3_AVAILABLE = True
            addr = "0x742d35Cc6634C0532925a3b844Bc9e7595f0eB1E"
            result = normalizer_module._eth_checksum(addr)
            self.assertEqual(result, addr.lower())

    def test_module_importable_without_web3(self):
        """Module is importable even if web3 is not installed."""
        with patch("extractor.normalizer.WEB3_AVAILABLE", False):
            import importlib
            import extractor.normalizer as normalizer_module

            importlib.reload(normalizer_module)

            self.assertFalse(normalizer_module.WEB3_AVAILABLE)
            self.assertTrue(callable(normalizer_module._eth_checksum))


class TestNormalizeEntities(unittest.TestCase):
    """Test entity normalization via normalize_entities()."""

    def test_normalize_ethereum_address(self):
        """Ethereum addresses are normalized correctly."""
        from extractor.normalizer import normalize_entities

        raw_entities = {
            "ETHEREUM_ADDRESS": ["0x742d35Cc6634C0532925a3b844Bc9e7595f0eB1E"]
        }

        result = normalize_entities(raw_entities, "http://example.com")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].entity_type, "ETHEREUM_ADDRESS")

    def test_normalize_bitcoin_address(self):
        """Bitcoin addresses are normalized correctly."""
        from extractor.normalizer import normalize_entities

        raw_entities = {
            "BITCOIN_ADDRESS": ["bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh"]
        }

        result = normalize_entities(raw_entities, "http://example.com")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].entity_type, "BITCOIN_ADDRESS")

    def test_normalize_email(self):
        """Email addresses are lowercased."""
        from extractor.normalizer import normalize_entities

        raw_entities = {
            "EMAIL_ADDRESS": ["User@Example.COM"]
        }

        result = normalize_entities(raw_entities, "http://example.com")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].value, "user@example.com")

    def test_normalize_cve(self):
        """CVE numbers are uppercased."""
        from extractor.normalizer import normalize_entities

        raw_entities = {
            "CVE_NUMBER": ["cve-2024-1234"]
        }

        result = normalize_entities(raw_entities, "http://example.com")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].value, "CVE-2024-1234")


class TestCanonicalizeEntityValue(unittest.TestCase):
    """Test canonical value generation for deduplication."""

    def test_ethereum_canonical(self):
        """Ethereum canonical form is lowercase."""
        from extractor.normalizer import canonicalize_entity_value

        result = canonicalize_entity_value("ETHEREUM_ADDRESS", "0x742d35Cc6634C0532925a3b844Bc9e7595f0eB1E")
        self.assertEqual(result, "0x742d35cc6634c0532925a3b844bc9e7595f0eb1e")

    def test_bitcoin_canonical_legacy(self):
        """Bitcoin legacy addresses preserve case (Base58 is case-sensitive)."""
        from extractor.normalizer import canonicalize_entity_value

        result = canonicalize_entity_value("BITCOIN_ADDRESS", "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")
        self.assertEqual(result, "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")

    def test_threat_actor_canonical(self):
        """Threat actor handles are normalized (lowercase, no separators)."""
        from extractor.normalizer import canonicalize_entity_value

        result = canonicalize_entity_value("THREAT_ACTOR_HANDLE", "Lazarus-Group")
        self.assertEqual(result, "lazarusgroup")


class TestValidateOnionUrl(unittest.TestCase):
    """Test _validate_onion_url() and its integration in normalize_entities()."""

    def test_clearnet_domain_is_rejected(self):
        """A plain clearnet domain must not pass onion validation."""
        from extractor.normalizer import _validate_onion_url
        self.assertFalse(_validate_onion_url("cdprojektred.com"))

    def test_http_v2_onion_is_accepted(self):
        """A well-formed v2 onion URL with http prefix is valid."""
        from extractor.normalizer import _validate_onion_url
        self.assertTrue(_validate_onion_url("http://facebookcorewwwi.onion"))

    def test_v3_onion_no_prefix_is_accepted(self):
        """A well-formed v3 onion address without a scheme is valid."""
        from extractor.normalizer import _validate_onion_url
        self.assertTrue(_validate_onion_url("facebookwkhpilnemxj7ascrwwwwi.onion"))

    def test_onion_subdomain_of_clearnet_is_rejected(self):
        """A domain like notanonion.onion.example.com must be rejected."""
        from extractor.normalizer import _validate_onion_url
        self.assertFalse(_validate_onion_url("notanonion.onion.example.com"))

    def test_clearnet_domain_classified_as_onion_url_is_discarded(self):
        """normalize_entities() must drop a clearnet domain tagged as ONION_URL."""
        from extractor.normalizer import normalize_entities
        raw = {"ONION_URL": ["cdprojektred.com"]}
        result = normalize_entities(raw, "http://example.onion")
        self.assertEqual(len(result), 0)

    def test_valid_onion_url_is_kept(self):
        """normalize_entities() must keep a legitimate onion URL."""
        from extractor.normalizer import normalize_entities
        raw = {"ONION_URL": ["http://facebookcorewwwi.onion"]}
        result = normalize_entities(raw, "http://example.onion")
        self.assertEqual(len(result), 1)

    def test_onion_subdomain_of_clearnet_is_discarded(self):
        """normalize_entities() must drop a fake-onion clearnet subdomain."""
        from extractor.normalizer import normalize_entities
        raw = {"ONION_URL": ["notanonion.onion.example.com"]}
        result = normalize_entities(raw, "http://example.onion")
        self.assertEqual(len(result), 0)


if __name__ == "__main__":
    unittest.main()
