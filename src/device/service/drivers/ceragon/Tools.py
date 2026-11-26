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
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

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
KPI_RADIO_RX_LEVEL_DBM = 801
KPI_RADIO_TX_LEVEL_DBM = 802
KPI_RADIO_SNIR_DB = 803
KPI_RADIO_MSE_DB = 804
KPI_RADIO_XPI_DB = 805
KPI_RADIO_TX_MODULATION_ORDER = 806
KPI_RADIO_TX_MCS_INDEX = 807
KPI_RADIO_RX_MCS_INDEX = 808
KPI_RADIO_TX_PER_PERCENT = 809
KPI_RADIO_RX_PER_PERCENT = 810
KPI_RADIO_ERRORED_SECONDS = 811
KPI_RADIO_SEVERELY_ERRORED_SECONDS = 812
KPI_RADIO_UNAVAILABLE_SECONDS = 813
KPI_RADIO_BACKGROUND_BLOCK_ERRORS = 814

KPI_METRIC_NAMES: Dict[int, str] = {
    KPI_PACKETS_TRANSMITTED: "packets_transmitted",
    KPI_PACKETS_RECEIVED: "packets_received",
    KPI_BYTES_TRANSMITTED: "bytes_transmitted",
    KPI_BYTES_RECEIVED: "bytes_received",
    KPI_LINK_TOTAL_CAPACITY_GBPS: "link_total_capacity_gbps",
    KPI_LINK_USED_CAPACITY_GBPS: "link_used_capacity_gbps",
    KPI_RADIO_RX_LEVEL_DBM: "radio_rx_level_dbm",
    KPI_RADIO_TX_LEVEL_DBM: "radio_tx_level_dbm",
    KPI_RADIO_SNIR_DB: "radio_snir_db",
    KPI_RADIO_MSE_DB: "radio_mse_db",
    KPI_RADIO_XPI_DB: "radio_xpi_db",
    KPI_RADIO_TX_MODULATION_ORDER: "radio_tx_modulation_order",
    KPI_RADIO_TX_MCS_INDEX: "radio_tx_mcs_index",
    KPI_RADIO_RX_MCS_INDEX: "radio_rx_mcs_index",
    KPI_RADIO_TX_PER_PERCENT: "radio_tx_per_percent",
    KPI_RADIO_RX_PER_PERCENT: "radio_rx_per_percent",
    KPI_RADIO_ERRORED_SECONDS: "radio_errored_seconds",
    KPI_RADIO_SEVERELY_ERRORED_SECONDS: "radio_severely_errored_seconds",
    KPI_RADIO_UNAVAILABLE_SECONDS: "radio_unavailable_seconds",
    KPI_RADIO_BACKGROUND_BLOCK_ERRORS: "radio_background_block_errors",
}

ETHERNET_SAMPLE_TYPES = (KPI_BYTES_TRANSMITTED, KPI_BYTES_RECEIVED)
RADIO_SAMPLE_TYPES = (KPI_LINK_TOTAL_CAPACITY_GBPS, KPI_LINK_USED_CAPACITY_GBPS)

# Error performance counters, read from the device's PM bins (ITU-T G.826 terms). The key
# is the leaf of the ceragon-pm-telemetry bin that carries the count.
RADIO_PM_SAMPLE_TYPES: Dict[int, str] = {
    KPI_RADIO_ERRORED_SECONDS: "errored-seconds",
    KPI_RADIO_SEVERELY_ERRORED_SECONDS: "severely-errored-seconds",
    KPI_RADIO_UNAVAILABLE_SECONDS: "unavailable-seconds",
    KPI_RADIO_BACKGROUND_BLOCK_ERRORS: "background-block-errors",
}
PM_FLAVORS = ("ceraos",)              # product families whose PM bins the driver reads
PM_INTERVAL_SECONDS = 15 * 60

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


def sector_index_of(endpoint_name: str) -> int:
    """Sector index of a radio endpoint name such as ``rf-sector-2``."""
    return int(str(endpoint_name).rsplit("-", 1)[-1])


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
            radio_sample_types(spec),
        ))
    return resources


# Radio figures each product family's API reports, per radio endpoint. A figure the device
# leaves out at a given poll produces no sample for that poll.
FAMILY_RADIO_FIGURES: Dict[str, Tuple[int, ...]] = {
    "siklu_tg": (KPI_RADIO_RX_LEVEL_DBM, KPI_RADIO_SNIR_DB, KPI_RADIO_TX_MODULATION_ORDER,
                 KPI_RADIO_TX_MCS_INDEX, KPI_RADIO_RX_MCS_INDEX, KPI_RADIO_TX_PER_PERCENT,
                 KPI_RADIO_RX_PER_PERCENT),
    "siklu_eh": (KPI_RADIO_RX_LEVEL_DBM, KPI_RADIO_SNIR_DB, KPI_RADIO_TX_MODULATION_ORDER),
    "ceraos": (KPI_RADIO_RX_LEVEL_DBM, KPI_RADIO_TX_LEVEL_DBM, KPI_RADIO_SNIR_DB, KPI_RADIO_MSE_DB,
               KPI_RADIO_XPI_DB, KPI_RADIO_TX_MODULATION_ORDER),
}


def radio_sample_types(spec: Optional[ProductSpec]) -> Tuple[int, ...]:
    """KPI types of a radio endpoint: capacity, the family's radio figures and its PM counters."""
    flavor = spec.api_flavor if spec else ""
    kpis = RADIO_SAMPLE_TYPES + FAMILY_RADIO_FIGURES.get(flavor, ())
    if flavor in PM_FLAVORS:
        kpis += tuple(RADIO_PM_SAMPLE_TYPES)
    return kpis


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

# IEEE 802.11ad DMG single-carrier MCS set: MCS 1-5 pi/2-BPSK, 6-9 pi/2-QPSK, 10-12 pi/2-16QAM;
# MCS 0 is the control PHY (DBPSK).
_MCS_80211AD = {**{i: "bpsk" for i in range(0, 6)}, **{i: "qpsk" for i in range(6, 10)},
                **{i: "qam-16" for i in range(10, 13)}}
_MODULATION_ORDER = {"bpsk": 2, "qpsk": 4, "8psk": 8, "qam-16": 16}


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


def mcs_modulation_order(mcs: Optional[int]) -> Optional[int]:
    """Constellation size of an IEEE 802.11ad single-carrier MCS, for the MCS values it defines."""
    if mcs is None or int(mcs) not in _MCS_80211AD:
        return None
    return _MODULATION_ORDER[_MCS_80211AD[int(mcs)]]


def modulation_order(raw: Optional[str]) -> Optional[int]:
    """Constellation size of a device modulation string: 'qam-256', '1024QAM', 'QPSK' or 'MCS-9'."""
    if not raw:
        return None
    text = str(raw).lower().replace("_", "-")
    m = re.search(r"(\d+)\s*-?qam|qam-?(\d+)", text)
    if m:
        return int(m.group(1) or m.group(2))
    m = re.search(r"mcs-?(\d+)", text)
    if m:
        return mcs_modulation_order(int(m.group(1)))
    for name in ("8psk", "qpsk", "bpsk"):
        if name in text:
            return _MODULATION_ORDER[name]
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


def radio_figure(state: CeragonDeviceState, sector_index: int, kpi_sample_type: int) -> Optional[Union[int, float]]:
    """
    One radio figure of a sector, as the device reported it at the last poll. Link figures
    (MCS, packet error rate) come from the active link bound to the sector.
    """
    sector = next((s for s in state.sectors if s.index == sector_index), None)
    if sector is None:
        return None
    link = next((lnk for lnk in state.active_links if lnk.local_sector_index == sector_index), None)
    by_sector = {
        KPI_RADIO_RX_LEVEL_DBM: sector.rsl_dbm,
        KPI_RADIO_TX_LEVEL_DBM: sector.tsl_dbm,
        KPI_RADIO_SNIR_DB: sector.snr_db,
        KPI_RADIO_MSE_DB: sector.mse_db,
        KPI_RADIO_XPI_DB: sector.xpi_db,
    }
    if kpi_sample_type in by_sector:
        value = by_sector[kpi_sample_type]
        return float(value) if value is not None else None
    if kpi_sample_type == KPI_RADIO_TX_MODULATION_ORDER:
        if link is not None and link.mcs_tx is not None:
            return mcs_modulation_order(link.mcs_tx)
        return modulation_order(sector.current_modulation)
    if link is None:
        return None
    by_link = {
        KPI_RADIO_TX_MCS_INDEX: link.mcs_tx,
        KPI_RADIO_RX_MCS_INDEX: link.mcs_rx,
        KPI_RADIO_TX_PER_PERCENT: link.tx_per_pct,
        KPI_RADIO_RX_PER_PERCENT: link.rx_per_pct,
    }
    value = by_link.get(kpi_sample_type)
    if value is None:
        return None
    return int(value) if kpi_sample_type in (KPI_RADIO_TX_MCS_INDEX, KPI_RADIO_RX_MCS_INDEX) else float(value)


def _parse_date_and_time(text: Any) -> Optional[float]:
    """Seconds since the epoch of a YANG date-and-time, or None when it does not parse."""
    try:
        moment = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.timestamp()


def last_completed_pm_bin(bins: List[Dict[str, Any]], now: float) -> Optional[Tuple[float, Dict[str, Any]]]:
    """
    The most recent valid 15-minute PM bin that ended by ``now``, with its end time. A bin
    still open, marked invalid or without a start time is left out.
    """
    best: Optional[Tuple[float, Dict[str, Any]]] = None
    for pm_bin in bins or []:
        if pm_bin.get("validity") is False or str(pm_bin.get("period-type", "fifteen-min")) != "fifteen-min":
            continue
        start = _parse_date_and_time(pm_bin.get("start-time"))
        if start is None:
            continue
        end = start + PM_INTERVAL_SECONDS
        if end <= now and (best is None or end > best[0]):
            best = (end, pm_bin)
    return best


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
