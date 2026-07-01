"""Unit tests for the network device driver layer (mock transport, no hardware)."""

from __future__ import annotations

import json

import pytest

from app.drivers import DeviceTarget, get_driver, list_drivers
from app.drivers.registry import registry

ALL_PLATFORMS = list(registry.keys())


def _mock_target(platform: str) -> DeviceTarget:
    return DeviceTarget(
        platform=platform,
        host="device.example.com",
        port=22,
        username="admin",
        password="secret",
        transport="mock",
    )


def test_expected_platforms_registered():
    expected = {
        "cisco_ios_xe",
        "cisco_ios",
        "cisco_9800_wlc",
        "juniper_junos",
        "arista_eos",
        "brocade_icx",
        "dell_os",
        "hp_procurve",
        "ruckus_unleashed",
        "juniper_mist",
        "ruckus_smartzone",
        "extreme_site_engine",
    }
    assert expected.issubset(set(registry))


def test_list_drivers_sorted_and_complete():
    metas = list_drivers()
    assert len(metas) == len(registry)
    names = [m.display_name for m in metas]
    assert names == sorted(names)


@pytest.mark.parametrize("platform", ALL_PLATFORMS)
def test_mock_backup_returns_nonempty_text(platform):
    driver = get_driver(_mock_target(platform))
    config = driver.backup()
    assert isinstance(config, str)
    assert config.strip()


@pytest.mark.parametrize("platform", ALL_PLATFORMS)
def test_mock_test_connection_true(platform):
    assert get_driver(_mock_target(platform)).test_connection() is True


@pytest.mark.parametrize("platform", ALL_PLATFORMS)
def test_mock_apply_reports_applied(platform):
    driver = get_driver(_mock_target(platform))
    config = driver.backup()
    result = driver.apply(config, dry_run=False)
    assert result.applied is True
    assert result.log


@pytest.mark.parametrize("platform", ALL_PLATFORMS)
def test_mock_apply_dry_run_does_not_apply(platform):
    driver = get_driver(_mock_target(platform))
    result = driver.apply(driver.backup(), dry_run=True)
    assert result.applied is False


def test_rest_drivers_emit_valid_json():
    for platform in ("juniper_mist", "ruckus_smartzone", "extreme_site_engine"):
        config = get_driver(_mock_target(platform)).backup()
        # Should round-trip as JSON.
        json.loads(config)


def test_unknown_platform_raises():
    with pytest.raises(KeyError):
        get_driver(_mock_target("does_not_exist"))
