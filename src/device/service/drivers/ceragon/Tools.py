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
Helper Utilities for the Ceragon TeraFlowSDN Driver
===================================================
Turns parsed device state into the structures the TeraFlowSDN Device service
expects:

* endpoints as ``('/endpoints/endpoint[<uuid>]', {...})`` resources, each with
  its KPI sample types mapped to a monitoring resource key;
* initial configuration rules whose values are JSON objects;
* an RFC 8561 (``ietf-microwave-radio-link``) view of the radio carriers;
* KPI values for the monitoring resource keys.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from .models import CeragonDeviceState, NetworkInterface, RadioSector
from .portfolio import ProductSpec

# KPI sample types (values of proto/kpi_sample_types.proto). Kept as integers so this
# module imports without the compiled protobuf package.
KPI_PACKETS_TRANSMITTED = 101
KPI_PACKETS_RECEIVED = 102
KPI_BYTES_TRANSMITTED = 201
KPI_BYTES_RECEIVED = 202
KPI_LINK_TOTAL_CAPACITY_GBPS = 301
KPI_LINK_USED_CAPACITY_GBPS = 302

KPI_METRIC_NAMES: Dict[int, str] = {
    KPI_PACKETS_TRANSMITTED: "packets_transmitted",
    KPI_PACKETS_RECEIVED: "packets_received",
    KPI_BYTES_TRANSMITTED: "bytes_transmitted",
    KPI_BYTES_RECEIVED: "bytes_received",
    KPI_LINK_TOTAL_CAPACITY_GBPS: "link_total_capacity_gbps",
    KPI_LINK_USED_CAPACITY_GBPS: "link_used_capacity_gbps",
}

ETHERNET_SAMPLE_TYPES = (KPI_BYTES_TRANSMITTED, KPI_BYTES_RECEIVED)
RADIO_SAMPLE_TYPES = (KPI_LINK_TOTAL_CAPACITY_GBPS, KPI_LINK_USED_CAPACITY_GBPS)

RESOURCE_RFC8561 = "/microwave-radio-link"

ENDPOINT_KEY_TEMPLATE = "/endpoints/endpoint[{:s}]"
MONITOR_KEY_RE = re.compile(r"^/endpoints/endpoint\[(?P<endpoint>[^\]]+)\]/state/(?P<metric>[a-z0-9_]+)$")

# Interfaces that are not traffic endpoints: management host port, RF aggregate and
# per-peer RF interfaces (the radio is represented by its sectors), bonds and tunnels.
_NON_ENDPOINT_NAME_RE = re.compile(r"^(host|rf|rf-.*|bond.*|tunnel-\d+|lo\d*)$", re.IGNORECASE)
_NON_ENDPOINT_TYPES = ("host", "softwareloopback", "rf", "bond", "tunnel")


def radio_endpoint_name(sector_index: int) -> str:
    return f"rf-sector-{int(sector_index)}"


def is_radio_endpoint(name: str) -> bool:
    return str(name).lower().startswith("rf-sector-")


def is_traffic_interface(iface: NetworkInterface) -> bool:
    if _NON_ENDPOINT_NAME_RE.match(iface.name or ""):
        return False
    if_type = str(iface.if_type or "").lower().split(":")[-1]
    return if_type not in _NON_ENDPOINT_TYPES


def radio_endpoint_type(spec: Optional[ProductSpec], frequency_mhz: Optional[float] = None) -> str:
    """Endpoint type for a radio carrier, from the band in use or the product's primary band."""
    if spec:
        if frequency_mhz:
            ghz = frequency_mhz / 1000.0
            for band in spec.bands:
                if band.freq_min_ghz <= ghz <= band.freq_max_ghz:
                    return band.endpoint_type
        return spec.primary_band.endpoint_type
    if frequency_mhz:
        ghz = frequency_mhz / 1000.0
        if 57 <= ghz <= 71:
            return "radio-v-band"
        if 71 < ghz <= 86:
            return "radio-e-band"
        return "radio-mw"
    return "radio"


def ethernet_endpoint_type(iface: NetworkInterface) -> str:
    gbps = iface.speed_gbps
    if gbps >= 1:
        return f"ethernet-{int(gbps)}g"
    if gbps > 0:
        return f"ethernet-{int(round(gbps * 1000))}m"
    return "ethernet"


def monitor_key(endpoint_uuid: str, kpi_sample_type: int) -> str:
    return "{:s}/state/{:s}".format(ENDPOINT_KEY_TEMPLATE.format(endpoint_uuid), KPI_METRIC_NAMES[kpi_sample_type])


def _endpoint_resource(uuid: str, ep_type: str, sample_types: Tuple[int, ...]) -> Tuple[str, Dict[str, Any]]:
    return (
        ENDPOINT_KEY_TEMPLATE.format(uuid),
        {
            "uuid": uuid,
            "name": uuid,
            "type": ep_type,
            "sample_types": {kpi: monitor_key(uuid, kpi) for kpi in sample_types},
        },
    )


def compose_endpoints(state: CeragonDeviceState) -> List[Tuple[str, Dict[str, Any]]]:
    """Endpoints in the format consumed by TeraFlowSDN's ``populate_endpoints``."""
    spec = state.product_spec
    resources: List[Tuple[str, Dict[str, Any]]] = []
    for iface in state.interfaces:
        if not is_traffic_interface(iface):
            continue
        resources.append(_endpoint_resource(iface.name, ethernet_endpoint_type(iface), ETHERNET_SAMPLE_TYPES))
    for sector in state.sectors:
        resources.append(_endpoint_resource(
            radio_endpoint_name(sector.index),
            radio_endpoint_type(spec, sector.frequency_mhz),
            RADIO_SAMPLE_TYPES,
        ))
    return resources


def _sector_dict(sector: RadioSector) -> Dict[str, Any]:
    return {
        "index": sector.index,
        "admin_status": sector.admin_status,
        "frequency_mhz": sector.frequency_mhz,
        "channel_bandwidth_mhz": sector.channel_bandwidth_mhz,
        "antenna_mode": sector.antenna_mode,
        "tx_power_control": sector.tx_power_control,
        "current_modulation": sector.current_modulation,
        "rsl_dbm": sector.rsl_dbm,
        "tsl_dbm": sector.tsl_dbm,
        "snr_db": sector.snr_db,
        "modem_temperature_c": sector.modem_temperature_c,
        "rf_temperature_c": sector.rf_temperature_c,
    }


def compose_initial_config(state: CeragonDeviceState) -> List[Tuple[str, Dict[str, Any]]]:
    """Device-level configuration rules. Every value is a JSON object, as TeraFlowSDN requires."""
    spec = state.product_spec
    rules: List[Tuple[str, Dict[str, Any]]] = [
        ("/device/hardware_info", {
            "vendor": state.vendor,
            "model": state.model,
            "serial_number": state.serial_number,
            "hardware_rev": state.hardware_rev,
            "software_version": state.software_version,
            "node_name": state.node_name,
            "operation_mode": state.operation_mode,
            "uptime": state.uptime,
        }),
        ("/device/capabilities", spec.to_capabilities() if spec else {"model": state.model, "catalog_match": None}),
    ]
    for sector in state.sectors:
        rules.append((f"/radio/sector[{sector.index}]", _sector_dict(sector)))
    rules.append((RESOURCE_RFC8561, compose_rfc8561_view(state)))
    return rules


# ── RFC 8561 view ───────────────────────────────────────────────────────────────

_MCS_80211AD = {**{i: "bpsk" for i in range(0, 5)}, **{i: "qpsk" for i in range(5, 10)},
                **{i: "qam-16" for i in range(10, 13)}}


def coding_modulation_identity(raw: Optional[str]) -> Optional[str]:
    """Map a device modulation string to an ``ietf-microwave-types`` identity, if one fits."""
    if not raw:
        return None
    text = str(raw).lower().replace("_", "-")
    m = re.search(r"(\d+)\s*-?qam|qam-?(\d+)", text)
    if m:
        order = m.group(1) or m.group(2)
        return f"ietf-microwave-types:qam-{order}"
    if "qpsk" in text:
        return "ietf-microwave-types:qpsk"
    if "bpsk" in text:
        return "ietf-microwave-types:bpsk"
    m = re.search(r"mcs-?(\d+)", text)
    if m and int(m.group(1)) in _MCS_80211AD:
        return f"ietf-microwave-types:{_MCS_80211AD[int(m.group(1))]}"
    return None


def compose_rfc8561_view(state: CeragonDeviceState) -> Dict[str, Any]:
    """
    Radio carriers as RFC 8561 carrier terminations (RFC 7951 JSON).

    Follows the ``ietf-microwave-radio-link`` module bundled with this driver. Values
    the device does not report are left out rather than invented.
    """
    spec = state.product_spec
    band = spec.primary_band if spec else None
    interfaces: List[Dict[str, Any]] = []
    for sector in state.sectors:
        entry: Dict[str, Any] = {
            "name": radio_endpoint_name(sector.index),
            "type": "iana-if-type:microwaveCarrierTermination",
            "ietf-microwave-radio-link:tx-enabled": str(sector.admin_status).lower() != "down",
            "ietf-microwave-radio-link:polarization": (
                sector.polarity if sector.polarity in ("horizontal", "vertical") else "not-specified"
            ),
        }
        if sector.frequency_mhz:
            entry["ietf-microwave-radio-link:tx-frequency"] = int(round(sector.frequency_mhz * 1000))
        if sector.channel_bandwidth_mhz:
            entry["ietf-microwave-radio-link:channel-separation"] = int(round(sector.channel_bandwidth_mhz * 1000))
        tx_ctl = str(sector.tx_power_control or "").lower()
        if tx_ctl in ("auto", "atpc"):
            entry["ietf-microwave-radio-link:atpc"] = {"enabled": True}
        elif tx_ctl:
            try:
                entry["ietf-microwave-radio-link:rtpc"] = {"maximum-nominal-power": round(float(tx_ctl), 1)}
            except ValueError:
                pass
        if band is not None:
            entry["ietf-microwave-radio-link:capabilities"] = {
                "min-tx-frequency": int(band.freq_min_ghz * 1_000_000),
                "max-tx-frequency": int(band.freq_max_ghz * 1_000_000),
            }
        perf: Dict[str, Any] = {}
        if sector.tsl_dbm is not None:
            perf["actual-transmitted-level"] = round(float(sector.tsl_dbm), 1)
        if sector.rsl_dbm is not None:
            perf["actual-received-level"] = round(float(sector.rsl_dbm), 1)
        if sector.snr_db is not None:
            perf["actual-snir"] = round(float(sector.snr_db), 1)
        selected_cm = coding_modulation_identity(sector.current_modulation)
        if selected_cm:
            perf["selected-cm"] = selected_cm
        if perf:
            entry["ietf-microwave-radio-link:radio-performance"] = perf
        interfaces.append(entry)
    return {"ietf-interfaces:interfaces": {"interface": interfaces}}


# ── KPI values ──────────────────────────────────────────────────────────────────

def sector_capacity_gbps(state: CeragonDeviceState, sector_index: int) -> Optional[float]:
    """Air capacity of one radio sector: the active link's rate, else the catalog nominal."""
    link = next((lnk for lnk in state.active_links if lnk.local_sector_index == sector_index), None)
    if link is not None and link.speed_tx_mbps is not None:
        return round(float(link.speed_tx_mbps) / 1000.0, 6)
    spec = state.product_spec
    if spec is not None:
        return float(spec.max_capacity_gbps)
    return None


def ethernet_ingress_octets(state: CeragonDeviceState) -> int:
    """Octets received on traffic ports, the traffic offered to the radio."""
    return sum(i.in_octets for i in state.interfaces if is_traffic_interface(i))


def endpoint_counter(state: CeragonDeviceState, endpoint_name: str, kpi_sample_type: int) -> Optional[int]:
    iface = next((i for i in state.interfaces if i.name == endpoint_name), None)
    if iface is None:
        return None
    if kpi_sample_type == KPI_BYTES_TRANSMITTED:
        return iface.out_octets
    if kpi_sample_type == KPI_BYTES_RECEIVED:
        return iface.in_octets
    return None


def metric_to_kpi(metric_name: str) -> Optional[int]:
    for kpi, name in KPI_METRIC_NAMES.items():
        if name == metric_name:
            return kpi
    return None


def parse_resource_value(val: Any) -> Dict[str, Any]:
    """Safely decode a JSON resource value into a dictionary."""
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            decoded = json.loads(val)
        except Exception:  # pylint: disable=broad-except
            return {"raw_value": val}
        return decoded if isinstance(decoded, dict) else {"raw_value": decoded}
    if val is None:
        return {}
    return {"raw_value": val}
