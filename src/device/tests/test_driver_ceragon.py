# Copyright 2026 Ceragon Networks Ltd. & ETSI TeraFlowSDN Authors
#
# Licensed under the BSD 3-Clause License (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://opensource.org/licenses/BSD-3-Clause
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Unit Tests for the Ceragon Wireless Transport Driver
=====================================================
Runs the driver against a fake RESTCONF device that serves a MultiHaul TG
candidate datastore or a CeraOS /restconf/data datastore, and records every
write. Covers discovery, batched commits, deletion rules, monitoring and the
RFC 8561 view.
"""
from __future__ import annotations

import copy
import json
import sys
import threading
import types
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest

try:
    import device.service.drivers  # noqa: F401  (full TFS image: every driver dependency present)
except Exception:  # pylint: disable=broad-except
    # Slim test environment: load only the Ceragon driver package.
    _drivers_pkg = types.ModuleType("device.service.drivers")
    _drivers_pkg.__path__ = [str(Path(__file__).resolve().parents[1] / "service" / "drivers")]
    sys.modules["device.service.drivers"] = _drivers_pkg

from device.service.driver_api._Driver import RESOURCE_ENDPOINTS
from device.service.drivers.ceragon.CeragonDriver import CeragonDriver
from device.service.drivers.ceragon.schemas import get_all_schemas, list_available_schemas

ADDRESS = "192.0.2.10"   # RFC 5737 documentation address
BASE = f"http://{ADDRESS}:80"
CANDIDATE = f"{BASE}/restconf/ds/ietf-datastores:candidate"
RUNNING = f"{BASE}/restconf/ds/ietf-datastores:running"
CERAOS_DATA = f"{BASE}/restconf/data"
COMMIT = f"{BASE}/restconf/operations/ietf-netconf:commit"
DISCARD = f"{BASE}/restconf/operations/ietf-netconf:discard-changes"

TG_DATASTORE: Dict[str, Any] = {
    "radio-bridge-tg-system:system": {"name": "node-a", "state": {"product": "MH-T261", "uptime": "1d"}},
    "radio-bridge-tg-inventory:inventory": {"component": [{
        "physical-class": "chassis", "model-name": "MH-T261", "serial-num": "TEST-SERIAL-0001",
        "hardware-rev": "A0", "software-rev": "1.0.0", "mfg-name": "Ceragon",
    }]},
    "radio-bridge-tg-interfaces:interfaces": {"interface": [
        {"ifIndex": 1, "name": "host", "iftype": "host", "oper-status": "up"},
        {"ifIndex": 2, "name": "eth1", "iftype": "ethernet", "ifSpeed": 10_000_000_000, "admin-status": "up",
         "oper-status": "up", "ifInOctets": 1_000_000, "ifOutOctets": 2_000_000},
        {"ifIndex": 3, "name": "eth2", "iftype": "ethernet", "ifSpeed": 1_000_000_000, "admin-status": "up",
         "oper-status": "down", "ifInOctets": 0, "ifOutOctets": 0},
        {"ifIndex": 4, "name": "rf", "iftype": "rf", "oper-status": "up"},
    ]},
    "radio-bridge-tg-radio-common:radio-common": {
        "node-config": {"operation-mode": "DN", "tx-power-control": "auto"},
        "links": {"active": [{
            "remote-assigned-name": "node-b", "actual-local-sector-index": 1, "actual-remote-sector-index": 1,
            "rssi": -45.5, "snr": 21.0, "mcs-tx": 9, "mcs-rx": 9, "speed-tx": 1800, "speed-rx": 1800,
        }]},
        "sectors-config": {"sector": [{
            "index": 1, "admin-status": "up",
            "state": {"frequency": "60480", "antenna-mode": "beamforming", "mac-addr": "02:00:00:00:00:01",
                      "temperatures": {"modem-temperature": 50, "rf": [{"index": 1, "rf-temperature": 47}]}},
        }]},
    },
}

CERAOS_DATASTORE: Dict[str, Any] = {
    "ietf-system:system": {"hostname": "node-c"},
    "ietf-hardware:hardware": {"component": [{
        "class": "iana-hardware:chassis", "model-name": "IP-20C", "serial-num": "TEST-SERIAL-0002",
        "software-rev": "1.0.0", "hardware-rev": "B",
    }]},
    "ietf-interfaces:interfaces": {"interface": [
        {"name": "eth1", "type": "iana-if-type:ethernetCsmacd", "enabled": True, "speed": 1_000_000_000,
         "statistics": {"in-octets": 5000, "out-octets": 7000}},
    ]},
    "ceragon-radio-link:radio-link-cfg": {"carrier": [{
        "index": 1, "tx-frequency-khz": 18_000_000, "channel-bandwidth-mhz": 56, "rsl-dbm": -40.2,
        "tsl-dbm": 18.0, "mse-db": -38.0, "current-modulation": "1024QAM", "current-capacity-mbps": 900,
    }]},
}


class FakeResponse:
    def __init__(self, url: str, status_code: int = 200, payload: Optional[Any] = None) -> None:
        self.url = url
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload) if payload is not None else ""

    def json(self) -> Any:
        return copy.deepcopy(self._payload)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeDevice:
    """Minimal RESTCONF device: serves one datastore and records writes."""

    def __init__(self, flavor: str = "terragraph", auth_ok: bool = True, commit_ok: bool = True) -> None:
        self.flavor = flavor
        self.auth_ok = auth_ok
        self.commit_ok = commit_ok
        self.datastore = copy.deepcopy(TG_DATASTORE if flavor == "terragraph" else CERAOS_DATASTORE)
        self.calls: List[Tuple[str, str, Any]] = []
        self.closed = False

    def _datastore_url(self) -> str:
        return CANDIDATE if self.flavor == "terragraph" else CERAOS_DATA

    def get(self, url: str, timeout: Any = None, **_: Any) -> FakeResponse:
        self.calls.append(("GET", url, None))
        if not self.auth_ok:
            return FakeResponse(url, 401)
        if url == self._datastore_url():
            return FakeResponse(url, 200, {"ietf-restconf:data": self.datastore})
        return FakeResponse(url, 404, {"error": "not found"})

    def patch(self, url: str, json: Any = None, timeout: Any = None, **_: Any) -> FakeResponse:  # pylint: disable=redefined-outer-name
        self.calls.append(("PATCH", url, json))
        return FakeResponse(url, 204)

    def put(self, url: str, json: Any = None, timeout: Any = None, **_: Any) -> FakeResponse:  # pylint: disable=redefined-outer-name
        self.calls.append(("PUT", url, json))
        return FakeResponse(url, 204)

    def post(self, url: str, json: Any = None, timeout: Any = None, **_: Any) -> FakeResponse:  # pylint: disable=redefined-outer-name
        self.calls.append(("POST", url, json))
        if url == COMMIT and not self.commit_ok:
            return FakeResponse(url, 500, {"error": "commit rejected"})
        return FakeResponse(url, 204)

    def delete(self, url: str, timeout: Any = None, **_: Any) -> FakeResponse:
        self.calls.append(("DELETE", url, None))
        return FakeResponse(url, 204)

    def close(self) -> None:
        self.closed = True

    def writes(self, method: Optional[str] = None) -> List[Tuple[str, str, Any]]:
        return [c for c in self.calls if c[0] != "GET" and (method is None or c[0] == method)]


def make_driver(device: FakeDevice, **settings: Any) -> CeragonDriver:
    driver = CeragonDriver(address=ADDRESS, port=80, username="admin", password="admin", timeout=5, **settings)
    driver._client._session = device  # pylint: disable=protected-access
    return driver


@pytest.fixture
def tg():
    device = FakeDevice("terragraph")
    return make_driver(device), device


@pytest.fixture
def ceraos():
    device = FakeDevice("ceraos")
    return make_driver(device), device


# ── Lifecycle ──────────────────────────────────────────────────────────────────

def test_driver_initialization():
    driver = CeragonDriver(address=ADDRESS, port=80, username="admin", password="secret", timeout=5, model="IP-20C")
    assert driver.name == "ceragon"
    assert driver.address == ADDRESS
    assert driver._client.config.model_hint == "IP-20C"  # pylint: disable=protected-access
    assert driver._client.config.verify_tls is True  # pylint: disable=protected-access


def test_connect_detects_terragraph(tg):
    driver, _ = tg
    assert driver.Connect() is True
    assert driver.Connect() is True  # idempotent
    assert driver._client.device_flavor == "terragraph"  # pylint: disable=protected-access


def test_connect_detects_ceraos(ceraos):
    driver, _ = ceraos
    assert driver.Connect() is True
    assert driver._client.device_flavor == "ceraos"  # pylint: disable=protected-access


def test_connect_auth_failure():
    driver = make_driver(FakeDevice(auth_ok=False))
    assert driver.Connect() is False


def test_disconnect_closes_session(tg):
    driver, device = tg
    driver.Connect()
    assert driver.Disconnect() is True
    assert device.closed is True


# ── Discovery ──────────────────────────────────────────────────────────────────

def test_endpoints_come_from_the_live_datastore(tg):
    driver, _ = tg
    resources = dict(driver.GetConfig([RESOURCE_ENDPOINTS]))
    assert set(resources) == {
        "/endpoints/endpoint[eth1]", "/endpoints/endpoint[eth2]", "/endpoints/endpoint[rf-sector-1]",
    }
    eth1 = resources["/endpoints/endpoint[eth1]"]
    assert eth1["uuid"] == "eth1" and eth1["type"] == "ethernet-10g"
    assert eth1["sample_types"] == {
        201: "/endpoints/endpoint[eth1]/state/bytes_transmitted",
        202: "/endpoints/endpoint[eth1]/state/bytes_received",
    }
    radio = resources["/endpoints/endpoint[rf-sector-1]"]
    assert radio["type"] == "radio-v-band"
    assert radio["sample_types"] == {
        301: "/endpoints/endpoint[rf-sector-1]/state/link_total_capacity_gbps",
        302: "/endpoints/endpoint[rf-sector-1]/state/link_used_capacity_gbps",
    }


def test_initial_config_values_are_json_objects(tg):
    driver, _ = tg
    rules = driver.GetInitialConfig()
    assert rules, "expected device-level rules"
    assert all(isinstance(value, dict) for _, value in rules)
    rules = dict(rules)
    assert RESOURCE_ENDPOINTS not in rules
    hw = rules["/device/hardware_info"]
    assert hw["model"] == "MH-T261" and hw["serial_number"] == "TEST-SERIAL-0001" and hw["node_name"] == "node-a"
    assert rules["/device/capabilities"]["api_flavor"] == "siklu_tg"
    assert rules["/radio/sector[1]"]["frequency_mhz"] == 60480.0


def test_get_config_without_keys_returns_endpoints_and_device_rules(tg):
    driver, _ = tg
    keys = [k for k, _ in driver.GetConfig()]
    assert "/endpoints/endpoint[eth1]" in keys and "/device/hardware_info" in keys


def test_rfc8561_view(tg):
    driver, _ = tg
    view = dict(driver.GetConfig(["/microwave-radio-link"]))["/microwave-radio-link"]
    (carrier,) = view["ietf-interfaces:interfaces"]["interface"]
    assert carrier["name"] == "rf-sector-1"
    assert carrier["type"] == "iana-if-type:microwaveCarrierTermination"
    assert carrier["ietf-microwave-radio-link:tx-frequency"] == 60_480_000  # kHz
    assert carrier["ietf-microwave-radio-link:atpc"] == {"enabled": True}
    perf = carrier["ietf-microwave-radio-link:radio-performance"]
    assert perf["actual-received-level"] == -45.5
    assert perf["actual-snir"] == 21.0
    assert perf["selected-cm"] == "ietf-microwave-types:qpsk"  # 802.11ad MCS 9


def test_ceraos_discovery_and_rfc8561(ceraos):
    driver, _ = ceraos
    resources = dict(driver.GetConfig([RESOURCE_ENDPOINTS, "/microwave-radio-link"]))
    assert "/endpoints/endpoint[eth1]" in resources
    assert resources["/endpoints/endpoint[rf-sector-1]"]["type"] == "radio-mw"
    (carrier,) = resources["/microwave-radio-link"]["ietf-interfaces:interfaces"]["interface"]
    assert carrier["ietf-microwave-radio-link:tx-frequency"] == 18_000_000
    assert carrier["ietf-microwave-radio-link:channel-separation"] == 56_000
    assert carrier["ietf-microwave-radio-link:radio-performance"]["selected-cm"] == "ietf-microwave-types:qam-1024"


# ── Configuration ──────────────────────────────────────────────────────────────

def test_slice_stages_a_bridge_and_commits_once(tg):
    driver, device = tg
    results = driver.SetConfig([(
        "/slice[svc-a]",
        json.dumps({"vlan_id": 200, "slice_name": "svc-a", "bandwidth_mbps": 500, "endpoints": ["eth1", "rf-sector-1"]}),
    )])
    assert results == [True]
    patches = device.writes("PATCH")
    assert len(patches) == 1
    url, payload = patches[0][1], patches[0][2]
    assert url.startswith(CANDIDATE + "/radio-bridge-tg-user-bridge:user-bridge/bridge=")
    ports = payload["radio-bridge-tg-user-bridge:bridge"][0]["bridge-port"]
    assert [p["interface"] for p in ports] == ["eth1", "rf"]
    assert all(p["c-vlan"] == 200 for p in ports)
    assert [c[1] for c in device.writes("POST")] == [COMMIT]


def test_one_failed_rule_discards_the_whole_request(tg):
    driver, device = tg
    results = driver.SetConfig([
        ("/interface[name=eth1]/slice[svc-b]", {"vlan_id": 300}),
        ("/interface[name=rf-sector-1]/radio", {"frequency_mhz": 18000}),  # outside the V-band
    ])
    assert all(isinstance(r, Exception) for r in results)
    assert "discarded" in str(results[0])
    assert "outside" in str(results[1])
    posts = [c[1] for c in device.writes("POST")]
    assert DISCARD in posts and COMMIT not in posts


def test_failed_commit_reports_every_staged_rule(tg):
    _, device = tg
    device.commit_ok = False
    driver = make_driver(device)
    results = driver.SetConfig([("/slice[svc-c]", {"vlan_id": 310})])
    assert isinstance(results[0], Exception) and "commit failed" in str(results[0])


def test_portfolio_gate_rejects_unsupported_domain(ceraos):
    driver, device = ceraos
    results = driver.SetConfig([("/interface[name=rf-sector-1]/beamforming", {"sector_index": 1})])
    assert isinstance(results[0], Exception) and "does not support" in str(results[0])
    assert device.writes() == []


def test_read_only_state_is_never_written_back(tg):
    driver, device = tg
    results = driver.SetConfig([("/radio/sector[1]", {"frequency_mhz": 58320.0}),
                                ("/device/hardware_info", {"model": "x"})])
    assert results == [True, True]
    assert device.writes() == []


def test_ceraos_slice_writes_directly_without_commit(ceraos):
    driver, device = ceraos
    results = driver.SetConfig([("/slice[svc-d]", {"vlan_id": 120, "bandwidth_mbps": 400})])
    assert results == [True]
    (patch_call,) = device.writes("PATCH")
    assert patch_call[1] == f"{CERAOS_DATA}/ceragon-slice:slice-config"
    entry = patch_call[2]["ceragon-slice:slice-config"]["slice"][0]
    assert entry["vlan-tag"] == 120 and entry["bandwidth-reservation-mbps"] == 400
    assert device.writes("POST") == []


def test_acm_and_radio_tuning_on_terragraph(tg):
    driver, device = tg
    results = driver.SetConfig([
        ("/interface[name=rf-sector-1]/acm", {"min_modulation": "MCS2", "max_modulation": "MCS12"}),
        ("/interface[name=rf-sector-1]/radio", {"frequency_mhz": 62640, "atpc_enabled": True}),
    ])
    assert results == [True, True]
    urls = [c[1] for c in device.writes("PATCH")]
    assert any(u.endswith("radio-bridge-tg-radio-common:radio-common/node-config") for u in urls)
    assert any(u.endswith("radio-bridge-tg-radio-dn:radio-dn/sectors-config/sector=1") for u in urls)
    assert [c[1] for c in device.writes("POST")] == [COMMIT]


def test_delete_removes_the_slice_and_keeps_radio_settings(tg):
    driver, device = tg
    results = driver.DeleteConfig([
        ("/slice[svc-a]", json.dumps({"vlan_id": 200, "slice_name": "svc-a"})),
        ("/interface[name=rf-sector-1]/acm", json.dumps({"min_modulation": "MCS2"})),
    ])
    assert results == [True, True]
    (delete_call,) = device.writes("DELETE")
    assert "radio-bridge-tg-user-bridge:user-bridge/bridge=" in delete_call[1]
    assert [c[1] for c in device.writes("POST")] == [COMMIT]


# ── Monitoring ─────────────────────────────────────────────────────────────────

KEY_TOTAL = "/endpoints/endpoint[rf-sector-1]/state/link_total_capacity_gbps"
KEY_USED = "/endpoints/endpoint[rf-sector-1]/state/link_used_capacity_gbps"
KEY_ETH_RX = "/endpoints/endpoint[eth1]/state/bytes_received"


def test_subscribe_rejects_unknown_keys(tg):
    driver, _ = tg
    results = driver.SubscribeState([("/endpoints/endpoint[eth1]/state/temperature", 0, 1),
                                     ("/device/telemetry", 0, 1)])
    assert all(isinstance(r, Exception) for r in results)


def test_capacity_and_counter_samples(tg):
    driver, device = tg
    first = {key: value for _, key, value in driver.collect_samples([KEY_TOTAL, KEY_USED, KEY_ETH_RX])}
    assert first[KEY_TOTAL] == 1.8          # active link speed-tx 1800 Mbps
    assert first[KEY_ETH_RX] == 1_000_000
    assert KEY_USED not in first            # needs two polls

    eth1 = device.datastore["radio-bridge-tg-interfaces:interfaces"]["interface"][1]
    eth1["ifInOctets"] += 125_000_000       # 1 Gbit offered to the radio
    second = {key: value for _, key, value in driver.collect_samples([KEY_USED])}
    assert second[KEY_USED] > 0


def test_sampler_streams_through_get_state(tg):
    driver, _ = tg
    assert driver.SubscribeState([(KEY_TOTAL, 0, 1.0), (KEY_ETH_RX, 0, 1.0)]) == [True, True]
    terminate = threading.Event()
    seen = set()
    timer = threading.Timer(8.0, terminate.set)
    timer.start()
    try:
        for _, key, _ in driver.GetState(blocking=True, terminate=terminate):
            seen.add(key)
            if {KEY_TOTAL, KEY_ETH_RX} <= seen:
                terminate.set()
    finally:
        timer.cancel()
        driver.Disconnect()
    assert {KEY_TOTAL, KEY_ETH_RX} <= seen


def test_unsubscribe(tg):
    driver, _ = tg
    driver.SubscribeState([(KEY_TOTAL, 0, 5.0)])
    assert driver.UnsubscribeState([(KEY_TOTAL, 0, 5.0)]) == [True]
    assert isinstance(driver.UnsubscribeState([(KEY_TOTAL, 0, 5.0)])[0], Exception)
    driver.Disconnect()


# ── Bundled YANG and catalog ────────────────────────────────────────────────────

def test_yang_schemas_completeness():
    from device.service.drivers.ceragon.schemas import validate_schema_closure
    from device.service.drivers.ceragon.portfolio import list_models, resolve_model

    schemas = list_available_schemas()
    assert len(schemas) == 84
    for name in ("radio-bridge-tg-radio-common", "ietf-interfaces", "ietf-datastores", "radio-bridge-tg-acm",
                 "ceragon-radio-link", "ceragon-qos", "ceragon-multiband", "ceragon-oran-xhaul",
                 "ietf-microwave-radio-link", "ietf-microwave-types"):
        assert name in schemas

    all_content = get_all_schemas()
    assert len(all_content) == 84
    for _, content in all_content.items():
        assert "module" in content

    ok, closure = validate_schema_closure()
    assert ok is True
    assert closure["closure_complete"] is True
    assert closure["missing_dependencies"] == {}

    all_models = list_models(include_fallbacks=True)
    assert len(all_models) == 36
    for spec in all_models:
        resolved = resolve_model(spec.model)
        assert resolved is not None
        assert resolved.family == spec.family
