from __future__ import annotations

from pathlib import Path

from framework.config.resolver import ConfigResolver
from framework.platform.adapters.linux import LinuxAdapter
from framework.platform.registry import PlatformRegistry


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_linux_adapter_executes_command() -> None:
    adapter = LinuxAdapter()

    result = adapter.execute(["/bin/echo", "platform-ok"])

    assert result.success is True
    assert result.stdout.strip() == "platform-ok"
    assert result.duration_ms >= 0


def test_linux_adapter_collects_system_info() -> None:
    info = LinuxAdapter().get_system_info()

    assert info["platform"] == "linux"
    assert "kernel" in info
    assert "machine" in info
    assert "hostname" in info


def test_platform_registry_builds_linux_capabilities_from_board_profile() -> None:
    board_profile = ConfigResolver(REPO_ROOT).resolve_fixture("fixtures/quick_validation.json").board_profile
    registry = PlatformRegistry()

    adapters, capabilities = registry.create_runtime_registries(board_profile)

    assert isinstance(adapters["linux"], LinuxAdapter)
    assert set(capabilities) >= {"network", "serial", "gpio", "i2c", "rtc", "system_info"}
    assert capabilities["system_info"].collect()["board_profile"] == "rk3576"


def test_capabilities_are_safe_when_devices_are_absent() -> None:
    board_profile = ConfigResolver(REPO_ROOT).resolve_fixture("fixtures/quick_validation.json").board_profile
    _, capabilities = PlatformRegistry().create_runtime_registries(board_profile)

    network_interfaces = capabilities["network"].list_interfaces(include_loopback=True)
    serial_ports = capabilities["serial"].list_ports()
    gpio_chips = capabilities["gpio"].list_chips()
    i2c_buses = capabilities["i2c"].list_buses()
    rtc_devices = capabilities["rtc"].list_devices()

    assert isinstance(network_interfaces, list)
    assert "lo" in network_interfaces
    assert isinstance(serial_ports, list)
    assert isinstance(gpio_chips, list)
    assert isinstance(i2c_buses, list)
    assert isinstance(rtc_devices, list)


def test_network_capability_prefers_board_profile_candidates() -> None:
    board_profile = ConfigResolver(REPO_ROOT).resolve_fixture("fixtures/quick_validation.json").board_profile
    _, capabilities = PlatformRegistry().create_runtime_registries(board_profile)

    resolved = capabilities["network"].resolve_primary(["definitely-missing-interface", "lo"])

    assert resolved == "lo"
