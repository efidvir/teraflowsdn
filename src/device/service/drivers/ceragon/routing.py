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
Config-rule routing for the Ceragon driver
==========================================
Maps one TeraFlowSDN config rule to the RESTCONF client call for its control
domain. Ported from the CER-Intent Ceragon adapter, whose payloads were checked
against hardware, so both paths configure a radio the same way.

Accepted resource keys:
  /interface[name=<if>]/<domain>            domain rule (README section 3)
  /interface[<if>]/<domain>[<instance>]     same, with an instance (e.g. one slice)
  /slice[<name>]                            device-wide transport slice
  /restconf/subtree/<path>                  direct RESTCONF PATCH / DELETE
  /rpc/<module>:<rpc>                       RESTCONF operation
Older keys such as /radio/tuning or /modulation/acm_floor are matched by keyword.

Deletion touches the device only for resources a service owns: slices (VLAN
bridges) and explicit /restconf/subtree/ paths. Radio-level settings (tuning,
ACM, sync, protection, ...) stay in place when a rule is removed, because
deleting them would take the link down for every service that rides on it.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from .client import CeragonRestClient
from .portfolio import ProductSpec, check_config_support
from .Tools import RESOURCE_RFC8561, is_radio_endpoint, parse_resource_value

LOGGER = logging.getLogger(__name__)

RuleResult = Tuple[bool, str, bool]  # (ok, message, device_changed)

_IFACE_KEY_RE = re.compile(
    r"^/interface\[(?:name=)?(?P<iface>[^\]]*)\]/(?P<ctype>[A-Za-z0-9_\-]+)(?:\[(?P<inst>[^\]]*)\])?$"
)
_SLICE_KEY_RE = re.compile(r"^/slice\[(?P<inst>[^\]]+)\]$")

# Keyword fallbacks for keys that do not follow the /interface[...]/<domain> form.
_KEYWORDS: List[Tuple[str, Tuple[str, ...]]] = [
    ("slice", ("slice", "vlan")),
    ("acm", ("/acm", "modulation", "rain")),
    ("radio", ("/radio", "frequency", "operating_parameters")),
    ("qos", ("qos", "tsn")),
    ("beamforming", ("beamforming",)),
    ("multiband", ("multiband", "bonding")),
    ("protection", ("protection", "xpic")),
    ("sync", ("sync", "ptp")),
    ("security", ("security", "macsec")),
    ("oran_xhaul", ("oran", "ecpri")),
    ("energy", ("energy",)),
]

# State the driver reports through GetInitialConfig. Writing it back is a no-op, so a
# device update that re-sends stored state never re-tunes the radio.
READ_ONLY_PREFIXES = ("/device/hardware_info", "/device/capabilities", "/device/endpoints",
                      "/radio/sector[", RESOURCE_RFC8561, "/endpoints")


def is_read_only(key: str) -> bool:
    return (key or "").startswith(READ_ONLY_PREFIXES)


_ALIASES = {"radio_tuning": "radio", "vlan": "slice", "tsn": "qos", "modulation": "acm", "interference": "protection"}


def config_type_from_key(key: str) -> Optional[str]:
    """Control domain addressed by a resource key, or None for pass-through keys."""
    key = key or ""
    if key.startswith("/restconf/subtree/") or key.startswith("/rpc/"):
        return None
    m = _IFACE_KEY_RE.match(key)
    if m:
        ctype = m.group("ctype").lower()
        return _ALIASES.get(ctype, ctype)
    if _SLICE_KEY_RE.match(key):
        return "slice"
    key_lower = key.lower()
    for ctype, words in _KEYWORDS:
        if any(w in key_lower for w in words):
            return ctype
    return None


def _gate_name(ctype: str, key: str) -> str:
    """Portfolio feature name for gating (XPIC requests are gated as 'interference')."""
    if ctype == "protection" and "xpic" in key.lower():
        return "interference"
    return ctype


def check_frequency(spec: Optional[ProductSpec], freq_mhz: Any) -> Tuple[bool, str]:
    if spec is None or freq_mhz in (None, ""):
        return True, "not checked"
    try:
        ghz = float(freq_mhz) / 1000.0
    except (TypeError, ValueError):
        return False, f"invalid frequency '{freq_mhz}'"
    for band in spec.bands:
        if band.freq_min_ghz <= ghz <= band.freq_max_ghz:
            return True, band.name
    bands = ", ".join(f"{b.name} {b.freq_min_ghz}-{b.freq_max_ghz} GHz" for b in spec.bands)
    return False, f"{ghz:.3f} GHz is outside {spec.model} band(s): {bands}"


def device_bridge_ports(client: CeragonRestClient, endpoints: Optional[List[str]]) -> Optional[List[str]]:
    """
    Device interface names for a slice. On MultiHaul TG / EtherHaul the radio side of a
    user bridge is the RF auto-connect interface "rf", so radio endpoints map to it.
    """
    if not endpoints:
        return None
    if client.device_flavor != "terragraph":
        return list(dict.fromkeys(endpoints))
    ports: List[str] = []
    for name in endpoints:
        port = "rf" if is_radio_endpoint(name) else name
        if port not in ports:
            ports.append(port)
    if "rf" not in ports:
        ports.append("rf")
    return ports


def _slice_params(key: str, val: Dict[str, Any]) -> Dict[str, Any]:
    m = _IFACE_KEY_RE.match(key or "") or _SLICE_KEY_RE.match(key or "")
    instance = m.group("inst") if m and "inst" in m.groupdict() else None
    vlan_id = int(val.get("vlan_id", val.get("vlan_tag", 100)))
    name = str(val.get("slice_name") or val.get("slice_id") or instance or f"slice-{vlan_id}")
    bandwidth = val.get("bandwidth_mbps")
    if bandwidth is None and val.get("min_throughput_gbps") is not None:
        bandwidth = float(val["min_throughput_gbps"]) * 1000
    # In /interface[name=<x>]/... keys CER-Intent puts the device id in <x>, so the
    # bridge ports come only from the rule value; without them the client uses its
    # default (first Ethernet port and the radio).
    endpoints = val.get("endpoints")
    s_vlan = val.get("s_vlan_id") or val.get("s_vlan_tag")
    return {
        "vlan_id": vlan_id,
        "slice_name": name,
        "bandwidth_mbps": int(bandwidth) if bandwidth is not None else None,
        "endpoints": endpoints,
        "s_vlan_id": int(s_vlan) if s_vlan else None,
        "bridge_id": int(val["bridge_id"]) if val.get("bridge_id") is not None else None,
    }


def apply_rule(client: CeragonRestClient, spec: Optional[ProductSpec], key: str, value: Any) -> RuleResult:
    """Stage one config rule on the device. The caller commits or discards the batch."""
    if is_read_only(key):
        return True, "Read-only device state; nothing to apply", False

    val = parse_resource_value(value)
    ctype = config_type_from_key(key)

    if ctype:
        supported, reason = check_config_support(spec, _gate_name(ctype, key))
        if not supported:
            return False, f"Rejected: {reason}", False

    if key.startswith("/restconf/subtree/"):
        ok, msg = client.apply_patch(key.removeprefix("/restconf/subtree/").strip("/"), val)
        return ok, msg, ok

    if key.startswith("/rpc/"):
        ok, out = client.invoke_rpc(key.removeprefix("/rpc/").strip("/"), val or None)
        return ok, json.dumps(out) if isinstance(out, dict) else str(out), False

    if ctype == "slice":
        p = _slice_params(key, val)
        ok, msg = client.apply_vlan_slice(
            vlan_id=p["vlan_id"],
            slice_name=p["slice_name"],
            bandwidth_mbps=p["bandwidth_mbps"],
            endpoints=device_bridge_ports(client, p["endpoints"]),
            bridge_id=p["bridge_id"],
            s_vlan_id=p["s_vlan_id"],
        )
        return ok, msg, ok

    if ctype == "radio":
        freq = val.get("tx_frequency") or val.get("frequency_mhz")
        ok_band, band_msg = check_frequency(spec, freq)
        if not ok_band:
            return False, f"Rejected: {band_msg}", False
        ok, msg = client.apply_radio_tuning(
            frequency_mhz=freq,
            tx_power_dbm=val.get("tx_power_dbm"),
            admin_status=val.get("admin_status"),
            script_id=val.get("mrmc_script_id"),
            channel_bandwidth_mhz=val.get("channel_bandwidth_mhz"),
            sector_index=int(val.get("sector_index", 1)),
            atpc_enabled=val.get("atpc_enabled"),
            polarity=val.get("polarity"),
        )
        return ok, msg, ok

    if ctype == "acm":
        ok, msg = client.apply_acm_config(
            min_modulation=val.get("min_modulation") or val.get("min_profile"),
            max_modulation=val.get("max_modulation") or val.get("max_profile") or val.get("target_modulation"),
            adaptive_enabled=bool(val.get("adaptive_enabled", val.get("acm_enabled", True))),
        )
        return ok, msg, ok

    if ctype == "qos":
        tsn = "tsn" in key.lower() or bool(val.get("tsn_enabled", False))
        cycle_ns = int(val.get("cycle_time_ns", int(float(val.get("cycle_time_us", 1000)) * 1000)))
        cir = val.get("cir_mbps") or val.get("bandwidth_mbps")
        pir = val.get("pir_mbps")
        ok, msg = client.apply_qos_tsn(
            qos_mode="tsn-scheduled" if tsn else "hierarchical-hqos",
            cir_mbps=int(cir) if cir else None,
            pir_mbps=int(pir) if pir else None,
            tsn_enabled=tsn,
            cycle_time_ns=cycle_ns,
            gate_control_list=val.get("gate_control_list"),
            preemption_8021qbu=bool(val.get("preemption_8021qbu", val.get("frame_preemption", False))),
        )
        return ok, msg, ok

    if ctype == "beamforming":
        golay = val.get("golay_index") or val.get("tx_golay_index")
        ok, msg = client.apply_beamforming(
            sector_index=int(val.get("sector_index", 1)),
            trigger_topo_scan=bool(val.get("trigger_topo_scan", True)),
            remote_assigned_name=val.get("remote_assigned_name"),
            tx_golay_index=int(golay) if golay is not None else None,
        )
        return ok, msg, ok

    if ctype == "multiband":
        ok, msg = client.apply_multiband_bonding(
            bond_name=str(val.get("bond_name", "bond-1")),
            member_interfaces=val.get("member_interfaces") or val.get("members"),
            bonding_mode=str(val.get("bonding_mode", "l1-radio-link-bonding")),
            min_priority_backup=int(val.get("min_priority_backup", 5)),
        )
        return ok, msg, ok

    if ctype == "protection":
        ok, msg = client.apply_protection(
            mode=str(val.get("protection_mode", val.get("mode", "one-plus-one-hsb"))),
            group_id=int(val.get("group_id", 1)),
            member_carriers=val.get("member_carriers"),
            revertive=bool(val.get("revertive", True)),
            trigger_switchover=bool(val.get("trigger_switchover", False)),
        )
        return ok, msg, ok

    if ctype == "sync":
        ok, msg = client.apply_sync_ptp(
            sync_mode=str(val.get("sync_mode", "ptp")),
            ptp_profile=str(val.get("ptp_profile", "itu-g8275-1")),
            domain_number=int(val.get("domain_number", 24)),
            synce_enabled=bool(val.get("synce_enabled", True)),
            ssm_quality=str(val.get("ssm_quality", "ql-prc")),
        )
        return ok, msg, ok

    if ctype == "security":
        ok, msg = client.apply_security_macsec(
            enabled=bool(val.get("enabled", True)),
            cipher_suite=str(val.get("cipher_suite", "gcm-aes-256")),
            sak_rekey_interval_sec=int(val.get("sak_rekey_interval_sec", 3600)),
            interfaces=val.get("interfaces"),
        )
        return ok, msg, ok

    if ctype == "oran_xhaul":
        ok, msg = client.apply_oran_xhaul(
            enabled=bool(val.get("enabled", True)),
            functional_split=str(val.get("functional_split", "split-7-2x-ecpri-fronthaul")),
            iq_compression=str(val.get("iq_compression", "bfp-9bit")),
            cti_enabled=bool(val.get("cti_enabled", True)),
            delay_budget_us=int(val.get("delay_budget_us", 100)),
            ecpri_vlan_id=int(val.get("ecpri_vlan_id", 10)),
        )
        return ok, msg, ok

    if ctype == "energy":
        ok, msg = client.apply_energy_policy(
            mode=str(val.get("mode", "green-atpc")),
            target_rsl_dbm=float(val.get("target_rsl_dbm", -42.0)),
            sleep_secondary_carriers=bool(val.get("sleep_secondary_carriers", False)),
        )
        return ok, msg, ok

    LOGGER.info("Ceragon driver: no control domain for %s; kept in the TFS config only", key)
    return True, "Kept in the TeraFlowSDN configuration only", False


def delete_rule(client: CeragonRestClient, key: str, value: Any) -> RuleResult:
    """Remove one config rule's effect from the device (service-owned resources only)."""
    if is_read_only(key):
        return True, "Read-only device state; nothing to remove", False
    val = parse_resource_value(value)
    if key.startswith("/restconf/subtree/"):
        ok, msg = client.apply_delete(key.removeprefix("/restconf/subtree/").strip("/"))
        return ok, msg, ok
    if config_type_from_key(key) == "slice":
        p = _slice_params(key, val)
        ok, msg = client.delete_vlan_slice(vlan_id=p["vlan_id"], slice_name=p["slice_name"], bridge_id=p["bridge_id"])
        return ok, msg, ok
    LOGGER.info("Ceragon driver: %s removed from the TFS config; radio-level setting left in place", key)
    return True, "Radio-level setting left in place", False
