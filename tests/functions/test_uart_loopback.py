from __future__ import annotations

from functions.uart.test_uart_loopback import test_uart_loopback as uart_loopback_function


class _FakeSerialCapability:
    def __init__(self) -> None:
        self.calls = []

    def loopback_test(self, port, *, payload, baudrate=115200, timeout=5):
        self.calls.append((port, payload, baudrate, timeout))
        return {
            "success": True,
            "port": port,
            "payload": payload,
            "message": "loopback ok",
            "received": payload,
            "matched": True,
            "baudrate": baudrate,
            "error_type": None,
            "duration_ms": 3,
        }


def test_uart_loopback_uses_serial_capability() -> None:
    capability = _FakeSerialCapability()

    result = uart_loopback_function(
        port="/dev/ttyS0",
        payload="phase-a",
        baudrate=115200,
        timeout=4,
        capability_registry={"serial": capability},
    )

    assert result["code"] == 0
    assert result["status"] == "passed"
    assert result["details"]["port"] == "/dev/ttyS0"
    assert result["details"]["received"] == "phase-a"
    assert result["details"]["matched"] is True
    assert result["metrics"]["payload_size"] == len("phase-a".encode("utf-8"))
    assert capability.calls == [("/dev/ttyS0", "phase-a", 115200, 4)]
