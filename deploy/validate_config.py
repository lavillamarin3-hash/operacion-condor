"""Validate the two network parameters without modifying the host."""

import argparse
import ipaddress


def validate_network(server_ip: str, lab_cidr: str) -> tuple[str, str]:
    private_ranges = tuple(
        ipaddress.IPv4Network(value)
        for value in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
    )
    try:
        address = ipaddress.IPv4Address(server_ip)
        network = ipaddress.IPv4Network(lab_cidr, strict=True)
    except ipaddress.AddressValueError as exc:
        raise ValueError("Usa una IPv4 y una subred IPv4 CIDR válidas.") from exc
    except ValueError as exc:
        raise ValueError("La subred debe estar normalizada, por ejemplo 192.168.146.0/24.") from exc
    if not any(address in block for block in private_ranges):
        raise ValueError("La IP del servidor debe pertenecer a una red privada RFC1918.")
    if not any(network.subnet_of(block) for block in private_ranges):
        raise ValueError("La subred del laboratorio debe estar dentro de una red privada RFC1918.")
    if network.prefixlen > 30:
        raise ValueError("Usa una subred con espacio para la víctima y Kali, por ejemplo /24.")
    if address not in network or address in (network.network_address, network.broadcast_address):
        raise ValueError("La IP del servidor debe ser una dirección de equipo dentro de la subred indicada.")
    return str(address), str(network)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server-ip", required=True)
    parser.add_argument("--lab-cidr", required=True)
    args = parser.parse_args()
    try:
        address, network = validate_network(args.server_ip, args.lab_cidr)
    except ValueError as exc:
        parser.error(str(exc))
    print(address)
    print(network)


if __name__ == "__main__":
    main()
