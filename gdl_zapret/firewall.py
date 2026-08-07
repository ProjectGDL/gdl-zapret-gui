import shutil

from .app_paths import (
    IPT_CHAIN,
    IPT_CHAIN_REPLY,
    IPT_TABLE,
    NFT_CHAIN,
    NFT_CHAIN_PRE,
    NFT_MARK,
    NFT_QUEUE_NUM,
    NFT_RULE_COMMENT,
    NFT_TABLE,
)
from .privileged import shq

class FirewallError(RuntimeError):
    pass

def available_backends() -> list:
    res = []
    if shutil.which("nft"):
        res.append("nftables")
    if shutil.which("iptables") and shutil.which("ip6tables"):
        res.append("iptables")
    return res

def detect_backend(preferred="auto"):
    if preferred != "auto" and preferred in available_backends():
        return preferred
    backends = available_backends()
    return backends[0] if backends else None

def _nft(tokens) -> str:
    return "nft " + " ".join(shq(t) for t in tokens)

def _nft_cleanup() -> str:
    return (
        f'if nft list tables 2>/dev/null | grep -q {shq(NFT_TABLE)}; then\n'
        f"  {_nft(['flush','chain',NFT_TABLE,NFT_CHAIN])} 2>/dev/null || true\n"
        f"  {_nft(['delete','chain',NFT_TABLE,NFT_CHAIN])} 2>/dev/null || true\n"
        f"  {_nft(['flush','chain',NFT_TABLE,NFT_CHAIN_PRE])} 2>/dev/null || true\n"
        f"  {_nft(['delete','chain',NFT_TABLE,NFT_CHAIN_PRE])} 2>/dev/null || true\n"
        f"  {_nft(['delete','table',NFT_TABLE])} 2>/dev/null || true\n"
        f"fi\n"
    )

def _nft_setup_script(tcp_ports, udp_ports, interface) -> str:
    oif = f'oifname "{interface}"' if interface and interface != "any" else ""
    iif = f'iifname "{interface}"' if interface and interface != "any" else ""
    comment = f'"{NFT_RULE_COMMENT}"'

    def rule(chain, iface_tok, proto, dports, direction, packet_range):
        tokens = [
            "add", "rule", NFT_TABLE, chain,
            *([iface_tok] if iface_tok else []),
            "meta", "mark", "and", NFT_MARK, "==", "0",
            proto, "dport", f"{{{dports}}}",
            "ct", direction, "packets", packet_range,
            "queue", "num", NFT_QUEUE_NUM, "bypass",
            "comment", comment,
        ]
        return _nft(tokens)

    lines = [_nft_cleanup(), "set -e"]
    lines.append(_nft(["add", "table", NFT_TABLE]))
    lines.append(
        _nft(["add", "chain", NFT_TABLE, NFT_CHAIN, "{", "type", "filter",
              "hook", "postrouting", "priority", "mangle;", "}"])
    )
    lines.append(
        _nft(["add", "chain", NFT_TABLE, NFT_CHAIN_PRE, "{", "type", "filter",
              "hook", "prerouting", "priority", "filter;", "}"])
    )
    if tcp_ports:
        lines.append(rule(NFT_CHAIN, oif, "tcp", tcp_ports, "original", "1-6"))
    if udp_ports:
        lines.append(rule(NFT_CHAIN, oif, "udp", udp_ports, "original", "1-6"))
    if tcp_ports:
        tokens = [
            "add", "rule", NFT_TABLE, NFT_CHAIN_PRE,
            *([iif] if iif else []),
            "tcp", "sport", f"{{{tcp_ports}}}",
            "ct", "reply", "packets", "1-3",
            "queue", "num", NFT_QUEUE_NUM, "bypass",
            "comment", comment,
        ]
        lines.append(_nft(tokens))
    return "\n".join(lines) + "\n"

def _nft_clear_script() -> str:
    return _nft_cleanup()

def _ipt_ports(ports: str) -> str:
    return ports.replace("{", "").replace("}", "").replace("-", ":")

def _ipt_setup_script(tcp_ports, udp_ports, interface) -> str:
    oif = f"-o {interface}" if interface and interface != "any" else ""
    tcp_ipt = _ipt_ports(tcp_ports)
    udp_ipt = _ipt_ports(udp_ports)
    mark = NFT_MARK

    body = []
    for cmd in ("iptables", "ip6tables"):
        for cleanup in (
            f"-t {IPT_TABLE} -D POSTROUTING -j {IPT_CHAIN}",
            f"-t {IPT_TABLE} -F {IPT_CHAIN}",
            f"-t {IPT_TABLE} -X {IPT_CHAIN}",
            f"-t {IPT_TABLE} -D PREROUTING -j {IPT_CHAIN_REPLY}",
            f"-t {IPT_TABLE} -F {IPT_CHAIN_REPLY}",
            f"-t {IPT_TABLE} -X {IPT_CHAIN_REPLY}",
        ):
            body.append(f"{cmd} {cleanup} 2>/dev/null || true")

    body.append("set -e")
    for cmd in ("iptables", "ip6tables"):
        body.append(f"{cmd} -t {IPT_TABLE} -N {IPT_CHAIN}")
        body.append(f"{cmd} -t {IPT_TABLE} -A POSTROUTING -j {IPT_CHAIN}")
        if tcp_ipt:
            body.append(
                f"{cmd} -t {IPT_TABLE} -A {IPT_CHAIN} {oif} -p tcp "
                f"-m multiport --dports {tcp_ipt} "
                f"-m connbytes --connbytes-dir=original --connbytes-mode=packets --connbytes 1:6 "
                f"-m mark ! --mark {mark} -j NFQUEUE --queue-num {NFT_QUEUE_NUM} --queue-bypass"
            )
        if udp_ipt:
            body.append(
                f"{cmd} -t {IPT_TABLE} -A {IPT_CHAIN} {oif} -p udp "
                f"-m multiport --dports {udp_ipt} "
                f"-m connbytes --connbytes-dir=original --connbytes-mode=packets --connbytes 1:6 "
                f"-m mark ! --mark {mark} -j NFQUEUE --queue-num {NFT_QUEUE_NUM} --queue-bypass"
            )
        if tcp_ipt:
            body.append(f"{cmd} -t {IPT_TABLE} -N {IPT_CHAIN_REPLY}")
            body.append(f"{cmd} -t {IPT_TABLE} -A PREROUTING -j {IPT_CHAIN_REPLY}")
            body.append(
                f"{cmd} -t {IPT_TABLE} -A {IPT_CHAIN_REPLY} {oif} -p tcp "
                f"-m multiport --sports {tcp_ipt} "
                f"-m connbytes --connbytes-dir=reply --connbytes-mode=packets --connbytes 1:3 "
                f"-m mark ! --mark {mark} -j NFQUEUE --queue-num {NFT_QUEUE_NUM} --queue-bypass"
            )
    return "\n".join(body) + "\n"

def _ipt_clear_script() -> str:
    body = []
    for cmd in ("iptables", "ip6tables"):
        for cleanup in (
            f"-t {IPT_TABLE} -D POSTROUTING -j {IPT_CHAIN}",
            f"-t {IPT_TABLE} -F {IPT_CHAIN}",
            f"-t {IPT_TABLE} -X {IPT_CHAIN}",
            f"-t {IPT_TABLE} -D PREROUTING -j {IPT_CHAIN_REPLY}",
            f"-t {IPT_TABLE} -F {IPT_CHAIN_REPLY}",
            f"-t {IPT_TABLE} -X {IPT_CHAIN_REPLY}",
        ):
            body.append(f"{cmd} {cleanup} 2>/dev/null || true")
    return "\n".join(body) + "\n"

def build_setup_script(backend, tcp_ports, udp_ports, interface) -> str:
    if backend == "nftables":
        return _nft_setup_script(tcp_ports, udp_ports, interface)
    if backend == "iptables":
        return _ipt_setup_script(tcp_ports, udp_ports, interface)
    raise FirewallError(f"Неизвестный firewall бэкенд: {backend}")

def build_clear_script(backend) -> str:
    if backend == "nftables":
        return _nft_clear_script()
    if backend == "iptables":
        return _ipt_clear_script()
    raise FirewallError(f"Неизвестный firewall бэкенд: {backend}")

def setup_firewall(elev, backend, tcp_ports, udp_ports, interface) -> tuple[bool, str]:
    script = build_setup_script(backend, tcp_ports, udp_ports, interface)
    try:
        r = elev.run_shell(script)
    except Exception as e:
        return False, str(e)
    output = (r.stdout or "") + (r.stderr or "")
    return r.returncode == 0, output

def clear_firewall(elev, backend) -> tuple[bool, str]:
    script = build_clear_script(backend)
    try:
        r = elev.run_shell(script)
    except Exception as e:
        return False, str(e)
    output = (r.stdout or "") + (r.stderr or "")
    return r.returncode == 0, output
