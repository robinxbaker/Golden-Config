"""SSH/CLI-based drivers powered by Netmiko (and NAPALM where available).

Each concrete driver supplies:
* class metadata (platform key, vendor, Netmiko device type, NAPALM driver),
* a realistic ``sample_config`` used by the mock transport,
* real backup/apply via the shared :class:`NetmikoDriver` mixin.
"""

from __future__ import annotations

from typing import ClassVar

from app.drivers.base import ApplyResult, BaseDriver, DriverError
from app.drivers.registry import register


class NetmikoDriver(BaseDriver):
    """Mixin implementing real SSH operations through Netmiko/NAPALM.

    Subclasses set :attr:`netmiko_device_type` and (optionally)
    :attr:`napalm_driver`. NAPALM is preferred for ``apply`` because it can compute a
    configuration diff and supports atomic replace/commit; Netmiko is the fallback.
    """

    transport_kind: ClassVar[str] = "ssh"
    netmiko_device_type: ClassVar[str]
    napalm_driver: ClassVar[str | None] = None
    backup_command: ClassVar[str] = "show running-config"

    def _connect_netmiko(self):
        # Imported lazily so the package imports cleanly without network libs at
        # collection time and so unit tests can run without them installed.
        from netmiko import ConnectHandler

        return ConnectHandler(
            device_type=self.netmiko_device_type,
            host=self.target.host,
            port=self.target.port,
            username=self.target.username or "",
            password=self.target.password or "",
            fast_cli=True,
        )

    def _real_test_connection(self) -> bool:
        try:
            conn = self._connect_netmiko()
            conn.disconnect()
            return True
        except Exception as exc:  # noqa: BLE001
            raise DriverError(f"SSH connection failed: {exc}") from exc

    def _real_backup(self) -> str:
        try:
            conn = self._connect_netmiko()
            try:
                return conn.send_command(self.backup_command)
            finally:
                conn.disconnect()
        except Exception as exc:  # noqa: BLE001
            raise DriverError(f"Backup failed: {exc}") from exc

    def _real_apply(self, config: str, dry_run: bool) -> ApplyResult:
        if self.napalm_driver:
            return self._apply_with_napalm(config, dry_run)
        return self._apply_with_netmiko(config, dry_run)

    def _apply_with_napalm(self, config: str, dry_run: bool) -> ApplyResult:
        from napalm import get_network_driver

        driver_cls = get_network_driver(self.napalm_driver)
        device = driver_cls(
            hostname=self.target.host,
            username=self.target.username or "",
            password=self.target.password or "",
            optional_args={"port": self.target.port},
        )
        try:
            device.open()
            device.load_merge_candidate(config=config)
            diff = device.compare_config()
            if dry_run:
                device.discard_config()
                return ApplyResult(diff=diff, applied=False, log="Dry run: candidate discarded.")
            device.commit_config()
            return ApplyResult(diff=diff, applied=True, log="Configuration committed via NAPALM.")
        except Exception as exc:  # noqa: BLE001
            raise DriverError(f"Apply failed: {exc}") from exc
        finally:
            device.close()

    def _apply_with_netmiko(self, config: str, dry_run: bool) -> ApplyResult:
        commands = [ln for ln in config.splitlines() if ln.strip()]
        if dry_run:
            diff = "\n".join(f"+ {ln}" for ln in commands)
            return ApplyResult(diff=diff, applied=False, log="Dry run: not sent to device.")
        try:
            conn = self._connect_netmiko()
            try:
                output = conn.send_config_set(commands)
                conn.save_config()
                return ApplyResult(diff=output, applied=True, log="Configuration sent via Netmiko.")
            finally:
                conn.disconnect()
        except Exception as exc:  # noqa: BLE001
            raise DriverError(f"Apply failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Concrete SSH drivers
# ---------------------------------------------------------------------------


@register
class CiscoIosXeDriver(NetmikoDriver):
    platform = "cisco_ios_xe"
    display_name = "Cisco IOS-XE (Catalyst 3850/9300)"
    vendor = "Cisco"
    netmiko_device_type = "cisco_xe"
    napalm_driver = "ios"

    def sample_config(self) -> str:
        return (
            "! Cisco IOS-XE running-config (mock)\n"
            f"hostname {self.target.host}\n"
            "!\n"
            "vtp mode transparent\n"
            "spanning-tree mode rapid-pvst\n"
            "!\n"
            "vlan 10\n name USERS\n"
            "vlan 20\n name VOICE\n"
            "vlan 99\n name MGMT\n"
            "!\n"
            "interface GigabitEthernet1/0/1\n"
            " description ACCESS-PORT\n"
            " switchport access vlan 10\n"
            " switchport mode access\n"
            " spanning-tree portfast\n"
            "!\n"
            "interface Vlan99\n"
            " ip address 10.99.0.2 255.255.255.0\n"
            "!\n"
            "ip default-gateway 10.99.0.1\n"
            "line vty 0 4\n"
            " transport input ssh\n"
            "end\n"
        )


@register
class CiscoIosDriver(NetmikoDriver):
    platform = "cisco_ios"
    display_name = "Cisco IOS"
    vendor = "Cisco"
    netmiko_device_type = "cisco_ios"
    napalm_driver = "ios"

    def sample_config(self) -> str:
        return (
            "! Cisco IOS running-config (mock)\n"
            f"hostname {self.target.host}\n"
            "spanning-tree mode pvst\n"
            "vlan 10\n name USERS\n"
            "interface FastEthernet0/1\n"
            " switchport mode access\n"
            " switchport access vlan 10\n"
            "interface Vlan1\n"
            " ip address 192.168.1.2 255.255.255.0\n"
            "line vty 0 4\n login local\n transport input ssh\n"
            "end\n"
        )


@register
class Cisco9800WlcDriver(NetmikoDriver):
    platform = "cisco_9800_wlc"
    display_name = "Cisco Catalyst 9800 WLC"
    vendor = "Cisco"
    netmiko_device_type = "cisco_xe"
    napalm_driver = "ios"

    def sample_config(self) -> str:
        return (
            "! Cisco C9800 WLC running-config (mock)\n"
            f"hostname {self.target.host}\n"
            "wireless management interface Vlan99\n"
            "wlan CORP-WIFI 1 CORP-WIFI\n"
            " security wpa psk set-key ascii 0 <redacted>\n"
            " no shutdown\n"
            "ap profile default-ap-profile\n"
            " description \"corporate APs\"\n"
            "wireless tag policy default-policy-tag\n"
            " wlan CORP-WIFI policy default-policy-profile\n"
            "end\n"
        )


@register
class JuniperJunosDriver(NetmikoDriver):
    platform = "juniper_junos"
    display_name = "Juniper Junos Switch"
    vendor = "Juniper"
    netmiko_device_type = "juniper_junos"
    napalm_driver = "junos"
    backup_command = "show configuration | display set"
    config_format = "set"

    def sample_config(self) -> str:
        return (
            "# Junos configuration (set format, mock)\n"
            f"set system host-name {self.target.host}\n"
            "set vlans USERS vlan-id 10\n"
            "set vlans VOICE vlan-id 20\n"
            "set interfaces ge-0/0/1 unit 0 family ethernet-switching vlan members USERS\n"
            "set interfaces irb unit 99 family inet address 10.99.0.2/24\n"
            "set protocols rstp\n"
            "set system services ssh\n"
        )


@register
class AristaEosDriver(NetmikoDriver):
    platform = "arista_eos"
    display_name = "Arista EOS"
    vendor = "Arista"
    netmiko_device_type = "arista_eos"
    napalm_driver = "eos"

    def sample_config(self) -> str:
        return (
            "! Arista EOS running-config (mock)\n"
            f"hostname {self.target.host}\n"
            "spanning-tree mode mstp\n"
            "vlan 10\n name USERS\n"
            "interface Ethernet1\n"
            " switchport access vlan 10\n"
            "interface Vlan99\n"
            " ip address 10.99.0.2/24\n"
            "management ssh\n"
            " no shutdown\n"
            "end\n"
        )


@register
class BrocadeIcxDriver(NetmikoDriver):
    platform = "brocade_icx"
    display_name = "Brocade / Ruckus ICX"
    vendor = "Brocade"
    netmiko_device_type = "ruckus_fastiron"

    def sample_config(self) -> str:
        return (
            "! Brocade/Ruckus ICX running-config (mock)\n"
            f"hostname {self.target.host}\n"
            "vlan 10 name USERS by port\n"
            " tagged ethernet 1/1/1\n"
            "interface ethernet 1/1/1\n"
            " port-name ACCESS\n"
            "ip address 10.99.0.2 255.255.255.0\n"
            "ssh access-group 10\n"
            "end\n"
        )


@register
class DellOsDriver(NetmikoDriver):
    platform = "dell_os"
    display_name = "Dell OS10/OS9"
    vendor = "Dell"
    netmiko_device_type = "dell_os10"

    def sample_config(self) -> str:
        return (
            "! Dell OS10 running-config (mock)\n"
            f"hostname {self.target.host}\n"
            "interface vlan10\n description USERS\n no shutdown\n"
            "interface ethernet1/1/1\n"
            " switchport access vlan 10\n no shutdown\n"
            "ip route 0.0.0.0/0 10.99.0.1\n"
            "end\n"
        )


@register
class HpProcurveDriver(NetmikoDriver):
    platform = "hp_procurve"
    display_name = "HP / Aruba ProCurve"
    vendor = "HPE"
    netmiko_device_type = "hp_procurve"

    def sample_config(self) -> str:
        return (
            "; HP ProCurve running-config (mock)\n"
            f"hostname {self.target.host}\n"
            "vlan 10\n name USERS\n untagged 1-12\n exit\n"
            "vlan 99\n name MGMT\n ip address 10.99.0.2 255.255.255.0\n exit\n"
            "spanning-tree\n"
            "ip ssh\n"
        )


@register
class RuckusUnleashedDriver(NetmikoDriver):
    platform = "ruckus_unleashed"
    display_name = "Ruckus Unleashed / ZoneDirector"
    vendor = "Ruckus"
    netmiko_device_type = "ruckus_fastiron"

    def sample_config(self) -> str:
        return (
            "! Ruckus Unleashed running-config (mock)\n"
            f"system name {self.target.host}\n"
            "wlan CORP-WIFI\n"
            " ssid CORP-WIFI\n"
            " type standard-usage\n"
            " encryption wpa2\n"
            "ap-group default\n"
            " radio 5g channel auto\n"
            "end\n"
        )
