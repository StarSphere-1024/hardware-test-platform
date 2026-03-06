from __future__ import annotations

from functions.network.test_eth_ping import test_eth_ping as eth_ping_function


class _FakeNetworkCapability:
    def __init__(self) -> None:
        self.calls = []

    def resolve_primary(self):
        return "eth0"

    def ping(self, target_ip, *, interface=None, count=1, timeout=5):
        self.calls.append((target_ip, interface, count, timeout))
        return {
            "success": True,
            "return_code": 0,
            "stdout": "1 packets transmitted, 1 received, 0% packet loss\nrtt min/avg/max/mdev = 0.010/1.234/2.000/0.100 ms\n",
            "stderr": "",
            "duration_ms": 8,
        }


def test_eth_ping_uses_capability_registry_and_parses_metrics() -> None:
    capability = _FakeNetworkCapability()

    result = eth_ping_function(
        target_ip="192.168.1.100",
        count=1,
        timeout=3,
        capability_registry={"network": capability},
    )

    assert result["code"] == 0
    assert result["status"] == "passed"
    assert result["details"]["interface"] == "eth0"
    assert result["metrics"]["packet_loss"] == 0.0
    assert result["metrics"]["avg_latency_ms"] == 1.234
    assert capability.calls == [("192.168.1.100", "eth0", 1, 3)]
