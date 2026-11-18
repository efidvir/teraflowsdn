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
Config rules for one Ceragon radio on a service path
====================================================
A radio hop carries an L2 or L3 service as a VLAN bridge between its Ethernet
port and its radio sector. The fixed rules:

* VLAN: the endpoint's own settings, else the service settings, else the VLAN
  used at the service's access points (``vlan_id`` for L2VPN, ``vlan_tag`` for
  L3VPN). A service without any VLAN is rejected.
* Bandwidth: ``bandwidth_mbps`` in the service settings, else the SLA capacity
  constraint, else left to the radio.
* Radio and ACM settings: taken from the service settings keys ``radio`` and
  ``acm`` when present (CER-Intent's slice controller decides them). Only the
  parameters listed below pass; anything else is dropped.
* Teardown removes the slice. Radio and ACM settings stay on the radio.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from common.tools.object_factory.ConfigRule import json_config_rule_delete, json_config_rule_set

RADIO_PARAMETERS = ("frequency_mhz", "channel_bandwidth_mhz", "tx_power_dbm", "atpc_enabled", "polarity",
                    "mrmc_script_id")
ACM_PARAMETERS = ("min_modulation", "max_modulation", "adaptive_enabled")

SLICE_KEY_TEMPLATE = "/slice[{:s}]"
RADIO_KEY_TEMPLATE = "/interface[name={:s}]/radio"
ACM_KEY_TEMPLATE = "/interface[name={:s}]/acm"


def _vlan_from(settings: Optional[Dict[str, Any]]) -> Optional[int]:
    if not settings:
        return None
    for field in ("vlan_id", "vlan_tag"):
        value = settings.get(field)
        if value is not None and str(value).strip() != "":
            return int(value)
    return None


def resolve_vlan(
    endpoint_settings: Iterable[Optional[Dict[str, Any]]],
    service_settings: Optional[Dict[str, Any]],
    access_point_settings: Iterable[Optional[Dict[str, Any]]],
) -> Optional[int]:
    for settings in endpoint_settings:
        vlan = _vlan_from(settings)
        if vlan is not None:
            return vlan
    vlan = _vlan_from(service_settings)
    if vlan is not None:
        return vlan
    for settings in access_point_settings:
        vlan = _vlan_from(settings)
        if vlan is not None:
            return vlan
    return None


def resolve_bandwidth_mbps(service_settings: Optional[Dict[str, Any]], capacity_gbps: Optional[float]) -> Optional[int]:
    if service_settings and service_settings.get("bandwidth_mbps") is not None:
        return int(service_settings["bandwidth_mbps"])
    if capacity_gbps:
        return int(round(float(capacity_gbps) * 1000))
    return None


def _allowed(values: Optional[Dict[str, Any]], names: Iterable[str]) -> Dict[str, Any]:
    if not isinstance(values, dict):
        return {}
    return {name: values[name] for name in names if values.get(name) is not None}


def radio_endpoints(endpoint_names: Iterable[str]) -> List[str]:
    return [name for name in endpoint_names if str(name).lower().startswith("rf-sector-")]


def compose_setup_rules(
    service_uuid: str, slice_name: str, vlan_id: int, bandwidth_mbps: Optional[int],
    endpoint_names: List[str], service_settings: Optional[Dict[str, Any]],
) -> List[Dict]:
    rules: List[Dict] = []
    radio = _allowed((service_settings or {}).get("radio"), RADIO_PARAMETERS)
    acm = _allowed((service_settings or {}).get("acm"), ACM_PARAMETERS)
    for name in radio_endpoints(endpoint_names):
        sector_index = int(name.rsplit("-", 1)[-1])
        if radio:
            rules.append(json_config_rule_set(RADIO_KEY_TEMPLATE.format(name), {**radio, "sector_index": sector_index}))
        if acm:
            rules.append(json_config_rule_set(ACM_KEY_TEMPLATE.format(name), acm))

    slice_value: Dict[str, Any] = {
        "vlan_id": int(vlan_id),
        "slice_name": slice_name,
        "endpoints": list(endpoint_names),
        "service_uuid": service_uuid,
    }
    if bandwidth_mbps is not None:
        slice_value["bandwidth_mbps"] = int(bandwidth_mbps)
    rules.append(json_config_rule_set(SLICE_KEY_TEMPLATE.format(service_uuid), slice_value))
    return rules


def compose_teardown_rules(
    service_uuid: str, slice_name: str, vlan_id: Optional[int], endpoint_names: List[str],
) -> List[Dict]:
    value: Dict[str, Any] = {"slice_name": slice_name, "endpoints": list(endpoint_names), "service_uuid": service_uuid}
    if vlan_id is not None:
        value["vlan_id"] = int(vlan_id)
    return [json_config_rule_delete(SLICE_KEY_TEMPLATE.format(service_uuid), value)]
