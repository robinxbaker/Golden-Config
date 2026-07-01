"""REST/controller-based drivers (httpx) for wireless and management controllers.

Controllers don't expose a CLI running-config; instead their "configuration" is a JSON
document fetched/pushed over HTTPS. The mock transport returns representative JSON so the
backup/apply flows behave identically to the SSH drivers.
"""

from __future__ import annotations

import json
from typing import Any, ClassVar

from app.drivers.base import ApplyResult, BaseDriver, DriverError
from app.drivers.registry import register


class RestControllerDriver(BaseDriver):
    """Mixin implementing real REST operations through httpx.

    Subclasses set :attr:`base_path` / :attr:`config_endpoint` and may override
    :meth:`_auth_headers` for token handling.
    """

    transport_kind: ClassVar[str] = "rest"
    config_format: ClassVar[str] = "json"
    default_port: ClassVar[int] = 443
    config_endpoint: ClassVar[str] = "/config"
    verify_tls: ClassVar[bool] = True

    def _base_url(self) -> str:
        return f"https://{self.target.host}:{self.target.port}"

    def _auth_headers(self) -> dict[str, str]:
        # Many controllers use a bearer token supplied as the device "password".
        token = self.target.password or ""
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def _client(self):
        import httpx

        return httpx.Client(
            base_url=self._base_url(),
            headers=self._auth_headers(),
            verify=self.verify_tls,
            timeout=30.0,
        )

    def _real_test_connection(self) -> bool:
        try:
            with self._client() as client:
                resp = client.get(self.config_endpoint)
                resp.raise_for_status()
            return True
        except Exception as exc:  # noqa: BLE001
            raise DriverError(f"REST connection failed: {exc}") from exc

    def _real_backup(self) -> str:
        try:
            with self._client() as client:
                resp = client.get(self.config_endpoint)
                resp.raise_for_status()
                return json.dumps(resp.json(), indent=2, sort_keys=True)
        except Exception as exc:  # noqa: BLE001
            raise DriverError(f"Backup failed: {exc}") from exc

    def _real_apply(self, config: str, dry_run: bool) -> ApplyResult:
        try:
            payload: Any = json.loads(config)
        except json.JSONDecodeError as exc:
            raise DriverError(f"Config is not valid JSON: {exc}") from exc

        if dry_run:
            return ApplyResult(
                diff=json.dumps(payload, indent=2, sort_keys=True),
                applied=False,
                log="Dry run: payload validated but not pushed.",
            )
        try:
            with self._client() as client:
                resp = client.put(self.config_endpoint, json=payload)
                resp.raise_for_status()
            return ApplyResult(diff="", applied=True, log="Configuration pushed via REST.")
        except Exception as exc:  # noqa: BLE001
            raise DriverError(f"Apply failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Concrete REST drivers
# ---------------------------------------------------------------------------


@register
class JuniperMistDriver(RestControllerDriver):
    platform = "juniper_mist"
    display_name = "Juniper Mist Controller"
    vendor = "Juniper"
    config_endpoint = "/api/v1/sites/config"

    def sample_config(self) -> str:
        return json.dumps(
            {
                "site": self.target.host,
                "wlans": [
                    {"ssid": "CORP-WIFI", "auth": "wpa2", "vlan_id": 10, "enabled": True},
                    {"ssid": "GUEST", "auth": "open", "vlan_id": 50, "enabled": True},
                ],
                "rf": {"band_24": {"power": "auto"}, "band_5": {"power": "auto"}},
                "switch_matching": {"enable": True},
            },
            indent=2,
            sort_keys=True,
        )


@register
class RuckusSmartZoneDriver(RestControllerDriver):
    platform = "ruckus_smartzone"
    display_name = "Ruckus SmartZone High-Scale"
    vendor = "Ruckus"
    config_endpoint = "/wsg/api/public/v11_1/rkszones/config"

    def sample_config(self) -> str:
        return json.dumps(
            {
                "zoneName": self.target.host,
                "wlans": [
                    {
                        "name": "CORP-WIFI",
                        "ssid": "CORP-WIFI",
                        "authType": "WPA2",
                        "vlanId": 10,
                    }
                ],
                "apGroups": [{"name": "default", "channelMode": "AUTO"}],
            },
            indent=2,
            sort_keys=True,
        )


@register
class ExtremeSiteEngineDriver(RestControllerDriver):
    platform = "extreme_site_engine"
    display_name = "Extreme Site Engine (XIQ-SE)"
    vendor = "Extreme"
    config_endpoint = "/nbi/v1/devices/config"

    def sample_config(self) -> str:
        return json.dumps(
            {
                "site": self.target.host,
                "policy": {"name": "Default Policy Domain", "roles": ["Enterprise User"]},
                "vlans": [
                    {"id": 10, "name": "USERS"},
                    {"id": 20, "name": "VOICE"},
                ],
                "ssids": [{"name": "CORP-WIFI", "security": "wpa2-enterprise"}],
            },
            indent=2,
            sort_keys=True,
        )
