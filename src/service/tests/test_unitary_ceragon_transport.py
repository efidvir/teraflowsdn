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
Unit tests for the Ceragon transport service handler
====================================================
L2 and L3 services cross a pair of Ceragon radios. The handler gets the radio
endpoints of the connection and writes, per radio, a VLAN bridge when the
service is tagged on the radio, plus the radio and ACM settings from the
service settings. Untagged services ride the radio's default bridge.
"""
from __future__ import annotations

import copy
import json
from typing import Dict, List

import pytest

from common.proto.context_pb2 import (
    ConfigActionEnum, Device, DeviceDriverEnum, DeviceId, Service, ServiceTypeEnum,
)
from common.tools.object_factory.ConfigRule import json_config_rule_set
from common.tools.object_factory.Constraint import json_constraint_sla_capacity
from common.tools.object_factory.Device import json_device, json_device_id
from common.tools.object_factory.EndPoint import json_endpoint_id
from common.tools.object_factory.Service import json_service_l2nm_planned, json_service_l3nm_planned
from service.service.service_handler_api.ServiceHandlerFactory import ServiceHandlerFactory, get_service_handler_class
from service.service.service_handlers import SERVICE_HANDLERS
from service.service.service_handlers.ceragon_transport.CeragonTransportServiceHandler import (
    CeragonTransportServiceHandler,
)


def _endpoint(device_uuid: str, endpoint_uuid: str, name: str, ep_type: str) -> Dict:
    return {
        "endpoint_id": json_endpoint_id(json_device_id(device_uuid), endpoint_uuid),
        "name": name,
        "endpoint_type": ep_type,
    }


def _radio(device_uuid: str) -> Device:
    return Device(**json_device(
        device_uuid, "ceragon-wireless", 2, name=device_uuid,
        endpoints=[
            _endpoint(device_uuid, f"{device_uuid}-eth1", "eth1", "ethernet-10g"),
            _endpoint(device_uuid, f"{device_uuid}-rf1", "rf-sector-1", "radio-v-band"),
        ],
        drivers=[DeviceDriverEnum.DEVICEDRIVER_CERAGON],
    ))


class FakeTaskExecutor:
    def __init__(self, devices: List[Device]) -> None:
        self.devices = {d.device_id.device_uuid.uuid: d for d in devices}
        self.configured: List[Device] = []

    def get_device(self, device_id: DeviceId) -> Device:
        device = Device()
        device.CopyFrom(self.devices[device_id.device_uuid.uuid])
        return device

    def configure_device(self, device: Device) -> None:
        snapshot = Device()
        snapshot.CopyFrom(device)
        self.configured.append(snapshot)


def _rules(device: Device) -> Dict[str, Dict]:
    return {
        r.custom.resource_key: {"action": r.action, "value": json.loads(r.custom.resource_value)}
        for r in device.device_config.config_rules
    }


SITE_SETTINGS = [
    json_config_rule_set("/device[pe-1]/endpoint[ge-0/0/1]/settings", {"vlan_tag": 300, "ip_address": "10.0.0.1"}),
    json_config_rule_set("/device[pe-2]/endpoint[ge-0/0/1]/settings", {"vlan_tag": 300, "ip_address": "10.0.0.2"}),
]
RADIO_PATH = [
    ("radio-a", "radio-a-eth1", None), ("radio-a", "radio-a-rf1", None),
    ("radio-b", "radio-b-rf1", None), ("radio-b", "radio-b-eth1", None),
]


def _l3vpn(settings: Dict = None, with_sites: bool = True, capacity_gbps: float = 0.5) -> Service:
    rules = copy.deepcopy(SITE_SETTINGS) if with_sites else []
    rules.append(json_config_rule_set("/settings", settings or {"address_families": ["IPV4"]}))
    service = Service(**json_service_l3nm_planned(
        "svc-l3vpn-1", constraints=[json_constraint_sla_capacity(capacity_gbps)], config_rules=rules))
    service.name = "site-a-to-site-b"
    return service


@pytest.fixture
def executor():
    return FakeTaskExecutor([_radio("radio-a"), _radio("radio-b")])


def test_handler_is_selected_for_l2nm_and_l3nm_on_ceragon_radios():
    factory = ServiceHandlerFactory(SERVICE_HANDLERS)
    radio = _radio("radio-a")
    device_and_drivers = {"radio-a": (radio, {DeviceDriverEnum.DEVICEDRIVER_CERAGON})}
    for service_json in (json_service_l3nm_planned("s1"), json_service_l2nm_planned("s2")):
        handler_class = get_service_handler_class(factory, Service(**service_json), device_and_drivers)
        assert handler_class is CeragonTransportServiceHandler


RADIO_SETTINGS = {
    "radio": {"frequency_mhz": 62640, "atpc_enabled": True, "not_a_radio_parameter": 1},
    "acm": {"min_modulation": "MCS4"},
}


def test_l3vpn_rides_the_default_bridge_and_gets_radio_settings(executor):
    # The sites use VLAN 300, but the routers terminate it: the radio carries the
    # router-to-router link as it arrives, so no slice is written.
    handler = CeragonTransportServiceHandler(_l3vpn({"address_families": ["IPV4"], **RADIO_SETTINGS}), executor)
    results = handler.SetEndpoint(list(RADIO_PATH), connection_uuid="conn-1")
    assert results == [True, True, True, True]
    assert [d.device_id.device_uuid.uuid for d in executor.configured] == ["radio-a", "radio-b"]
    rules = _rules(executor.configured[0])
    assert "/slice[svc-l3vpn-1]" not in rules
    assert rules["/interface[name=rf-sector-1]/radio"]["value"] == {
        "frequency_mhz": 62640, "atpc_enabled": True, "sector_index": 1,
    }
    assert rules["/interface[name=rf-sector-1]/acm"]["value"] == {"min_modulation": "MCS4"}


def test_l3vpn_with_an_explicit_radio_vlan(executor):
    handler = CeragonTransportServiceHandler(_l3vpn({"vlan_id": 310, **RADIO_SETTINGS}), executor)
    assert handler.SetEndpoint(list(RADIO_PATH)) == [True, True, True, True]
    slice_rule = _rules(executor.configured[0])["/slice[svc-l3vpn-1]"]
    assert slice_rule["action"] == ConfigActionEnum.CONFIGACTION_SET
    assert slice_rule["value"] == {
        "vlan_id": 310, "slice_name": "site-a-to-site-b", "bandwidth_mbps": 500,
        "endpoints": ["eth1", "rf-sector-1"], "service_uuid": "svc-l3vpn-1",
    }


def test_settings_bandwidth_wins_over_the_sla(executor):
    handler = CeragonTransportServiceHandler(_l3vpn({"vlan_id": 310, "bandwidth_mbps": 250}), executor)
    assert handler.SetEndpoint(list(RADIO_PATH[:2])) == [True, True]
    assert _rules(executor.configured[0])["/slice[svc-l3vpn-1]"]["value"]["bandwidth_mbps"] == 250


def test_l2vpn_service_vlan(executor):
    service = Service(**json_service_l2nm_planned(
        "svc-l2vpn-1", config_rules=[json_config_rule_set("/settings", {"vlan_id": 120})]))
    handler = CeragonTransportServiceHandler(service, executor)
    assert handler.SetEndpoint(list(RADIO_PATH[:2])) == [True, True]
    value = _rules(executor.configured[0])["/slice[svc-l2vpn-1]"]["value"]
    assert value["vlan_id"] == 120 and "bandwidth_mbps" not in value
    assert "/interface[name=rf-sector-1]/radio" not in _rules(executor.configured[0])


def test_l2vpn_takes_the_vlan_of_its_access_points(executor):
    service = Service(**json_service_l2nm_planned("svc-l2vpn-2", config_rules=[
        json_config_rule_set("/device[pe-1]/endpoint[ge-0/0/1]/settings", {"vlan_id": 125}),
        json_config_rule_set("/settings", {"mtu": 1500}),
    ]))
    handler = CeragonTransportServiceHandler(service, executor)
    assert handler.SetEndpoint(list(RADIO_PATH[:2])) == [True, True]
    assert _rules(executor.configured[0])["/slice[svc-l2vpn-2]"]["value"]["vlan_id"] == 125


def test_untagged_service_without_radio_settings_writes_nothing(executor):
    handler = CeragonTransportServiceHandler(_l3vpn(with_sites=False), executor)
    assert handler.SetEndpoint(list(RADIO_PATH)) == [True, True, True, True]
    assert executor.configured == []
    assert handler.DeleteEndpoint(list(RADIO_PATH)) == [True, True, True, True]
    assert executor.configured == []


def test_teardown_removes_only_the_slice(executor):
    handler = CeragonTransportServiceHandler(_l3vpn({"vlan_id": 310, **RADIO_SETTINGS}), executor)
    assert handler.DeleteEndpoint(list(RADIO_PATH)) == [True, True, True, True]
    for device in executor.configured:
        rules = _rules(device)
        assert list(rules) == ["/slice[svc-l3vpn-1]"]
        assert rules["/slice[svc-l3vpn-1]"]["action"] == ConfigActionEnum.CONFIGACTION_DELETE
        assert rules["/slice[svc-l3vpn-1]"]["value"]["vlan_id"] == 310
