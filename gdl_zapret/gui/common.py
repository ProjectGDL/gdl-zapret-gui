from pathlib import Path


def _iface_label(name: str) -> str:
    net = Path("/sys/class/net") / name

    if (net / "wireless").is_dir() or (net / "phy80211").is_dir():
        return f"Wi-Fi ({name})"

    type_file = net / "type"
    iface_type = None
    if type_file.exists():
        try:
            iface_type = int(type_file.read_text().strip())
        except ValueError:
            pass

    n = name.lower()

    if (net / "bridge").is_dir() or n.startswith("br") or n.startswith("virbr"):
        return f"Мост ({name})"

    if iface_type == 65534 or n.startswith("tun") or n.startswith("tap"):
        return f"VPN/TUN ({name})"

    if iface_type == 772 or n == "lo":
        return f"Loopback ({name})"

    if n.startswith("docker") or n.startswith("veth") or n.startswith("podman"):
        return f"Виртуальный ({name})"

    if n.startswith("wg") or n.startswith("tun") or n.startswith("vpn"):
        return f"VPN ({name})"

    if iface_type == 1 or n.startswith(("eno", "enp", "ens", "eth", "em")):
        return f"Ethernet ({name})"

    return name


def system_interfaces() -> list:
    net = Path("/sys/class/net")
    if net.is_dir():
        return sorted(p.name for p in net.iterdir())
    return []
