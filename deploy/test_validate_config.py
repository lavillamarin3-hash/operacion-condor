"""Network-boundary checks for the installer (standard library only)."""

import unittest

from validate_config import validate_network


class NetworkValidationTests(unittest.TestCase):
    def test_accepts_rfc1918_host_and_subnet(self):
        for address, network in (
            ("192.168.146.137", "192.168.146.0/24"),
            ("10.1.2.3", "10.1.2.0/24"),
            ("172.31.5.10", "172.31.5.0/24"),
            ("10.10.30.20", "10.10.20.0/24"),
        ):
            with self.subTest(address=address):
                self.assertEqual(validate_network(address, network), (address, network))

    def test_refuses_public_special_and_wildcard_addresses(self):
        for address in ("8.8.8.8", "0.0.0.0", "127.0.0.1", "169.254.1.2", "100.64.1.2", "::1"):
            with self.subTest(address=address), self.assertRaises(ValueError):
                validate_network(address, "192.168.146.0/24")

    def test_refuses_public_or_overbroad_network(self):
        for network in ("0.0.0.0/0", "192.168.0.0/15", "10.0.0.0/7", "8.8.8.0/24"):
            with self.subTest(network=network), self.assertRaises(ValueError):
                validate_network("192.168.146.137", network)

    def test_refuses_missing_host_noncanonical_subnet_and_injection(self):
        for address, network in (
            ("192.168.146.0", "192.168.146.0/24"),
            ("192.168.146.255", "192.168.146.0/24"),
            ("192.168.146.137", "192.168.146.137/24"),
            ("192.168.146.137", "192.168.146.137/32"),
            ("192.168.146.137;echo x", "192.168.146.0/24"),
        ):
            with self.subTest(address=address, network=network), self.assertRaises(ValueError):
                validate_network(address, network)


if __name__ == "__main__":
    unittest.main()
