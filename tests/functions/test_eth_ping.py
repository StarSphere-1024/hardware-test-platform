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
            "target": target_ip,
            "interface": interface,
            "return_code": 0,
            "stdout": "1 packets transmitted, 1 received, 0% packet loss\nrtt min/avg/max/mdev = 0.010/1.234/2.000/0.100 ms\n",
            "stderr": "",
            "packet_loss": 0.0,
            "avg_latency_ms": 1.234,
            "message": f"icmp probe to {target_ip} via {interface or 'auto'} ok",
            "duration_ms": 8,
        }


def test_eth_ping_uses_capability_registry_and_consumes_structured_metrics() -> None:
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


def test_eth_ping_does_not_require_linux_stdout_parsing() -> None:
    class _StructuredOnlyNetworkCapability(_FakeNetworkCapability):
        def ping(self, target_ip, *, interface=None, count=1, timeout=5):
            self.calls.append((target_ip, interface, count, timeout))
            return {
                "success": True,
                "target": target_ip,
                "interface": interface,
                "return_code": 0,
                "stdout": "",
                "stderr": "",
                "packet_loss": 12.5,
                "avg_latency_ms": 9.75,
                "message": "structured probe ok",
                "duration_ms": 12,
            }

    capability = _StructuredOnlyNetworkCapability()

    result = eth_ping_function(
        target_ip="192.168.1.100",
        count=2,
        timeout=4,
        capability_registry={"network": capability},
    )

    assert result["message"] == "ping 192.168.1.100 via eth0 ok"
    assert result["metrics"]["packet_loss"] == 12.5
    assert result["metrics"]["avg_latency_ms"] == 9.75
    assert capability.calls == [("192.168.1.100", "eth0", 2, 4)]
