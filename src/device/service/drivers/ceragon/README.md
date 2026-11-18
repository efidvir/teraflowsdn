# Ceragon Wireless Radio Transport Driver for ETSI TeraFlowSDN

The **Ceragon southbound driver** (`src/device/service/drivers/ceragon/`) lets TeraFlowSDN discover, monitor and configure Ceragon wireless transport equipment (MultiHaul TG, EtherHaul and CeraOS-based FibeAir nodes) over RFC 8040 RESTCONF.

Together with the **Ceragon transport service handler** (`src/service/service/service_handlers/ceragon_transport/`), services created through TeraFlowSDN's standard northbound interfaces (IETF Network Slice, RFC 9543; L2VPN, RFC 8466; L3VPN, RFC 8299) reach the radios on their path.

---

## 1. Module Structure

```
src/device/service/drivers/ceragon/
├── __init__.py          # Exports CeragonDriver
├── CeragonDriver.py     # TFS _Driver implementation: discovery, batched config, monitoring
├── client.py            # RESTCONF client: flavor detection, 2-phase commit, 12 control domains, PM, events
├── config.py            # Connection settings built from _connect/address, _connect/port, _connect/settings
├── models.py            # Parsed device state: interfaces, radio sectors, active links, PM samples
├── portfolio.py         # Ceragon product catalog and capability gating
├── routing.py           # Config rule -> control domain routing, deletion rules
├── Tools.py             # TFS endpoints, initial config, RFC 8561 view, KPI values
├── UPSTREAM_CHECKLIST.md
└── schemas/             # 84 bundled YANG 1.1 modules with dependency closure
```

`client.py`, `models.py` and the routing in `routing.py` are shared with the CER-Intent Ceragon adapter, whose payloads were checked against hardware, so both paths configure a radio the same way.

---

## 2. Supported Hardware

| Family | Model Series | Spectrum | Max Throughput | Transport Role |
| :--- | :--- | :--- | :--- | :--- |
| **MultiHaul TG** | `MH-T261` *(lab-verified)*, `MH-T260`, `MH-T265`, `MH-T280`, `MH-N265`, `MH-N366`, `MH-N367` | 57–71 GHz (V-Band) | Up to 7.2 Gbps | mmWave Mesh / PtMP / Terragraph |
| **EtherHaul** | `EH-614TX`, `EH-710TX`, `EH-1200TX`, `EH-1200FX`, `EH-2500FX`, `EH-8010FX`, `EH-8020FX` | 60 GHz (V-Band) / 70–80 GHz (E-Band) | Up to 20 Gbps | Ultra-High-Capacity PtP Carrier Link |
| **FibeAir IP-20** | `IP-20C`, `IP-20C-HP`, `IP-20S`, `IP-20E`, `IP-20V`, `IP-20N`, `IP-20A`, `IP-20A-LH`, `IP-20G`, `IP-20GX` | 4–86 GHz (MW / E-Band / V-Band) | Up to 10 Gbps | Split-Mount & All-Outdoor Microwave / Trunk |
| **IP-50** | `IP-50C`, `IP-50CX`, `IP-50E`, `IP-50EX`, `IP-50EXA`, `IP-50FX` | 6–42 GHz MW & 70/80 GHz E-Band | Up to 25 Gbps | Disaggregated Multi-Core MW, Multi-Band & Nodal |
| **IP-100** | `IP-100E` | 70/80 GHz (Dual-Carrier E-Band) | Up to 25 Gbps | Next-Gen Ultra-Capacity E-Band |

Catalog values other than the lab-verified model are nominal and should be checked against the datasheet.

---

## 3. Connection Settings

| Resource Key | Example | Notes |
| :--- | :--- | :--- |
| `_connect/address` | `192.0.2.10` | Management address of the radio. |
| `_connect/port` | `80` | `443`/`8443` imply HTTPS. HTTP-to-HTTPS redirects are followed and remembered. |
| `_connect/settings` | `{"username": "admin", "password": "...", "scheme": "https", "verify_tls": false, "timeout": 15, "model": "IP-50C"}` | `verify_tls` defaults to `true`. `model` is an optional hint used before the device reports its model. |

---

## 4. What the Driver Reports

### Endpoints (`GetConfig(['__endpoints__'])`)
Read from the live datastore, in the `('/endpoints/endpoint[<uuid>]', {...})` form that the Device service consumes:

| Endpoint | Source | Type | KPI sample types |
| :--- | :--- | :--- | :--- |
| `eth1`, `eth2`, ... | traffic ports (host, RF, bond and tunnel interfaces are skipped) | `ethernet-<speed>` | `BYTES_TRANSMITTED`, `BYTES_RECEIVED` |
| `rf-sector-<n>` | radio sectors / carriers | `radio-v-band`, `radio-e-band`, `radio-mw` | `LINK_TOTAL_CAPACITY_GBPS`, `LINK_USED_CAPACITY_GBPS` |

Monitoring keys follow the TFS convention `/endpoints/endpoint[<uuid>]/state/<kpi_name>`.

### Device configuration (`GetInitialConfig()`)
`/device/hardware_info`, `/device/capabilities`, `/radio/sector[<n>]` and `/microwave-radio-link`. All values are JSON objects. These keys are read-only: writing them back is a no-op, so a device update never re-tunes a radio from stored state.

### RFC 8561 view (`GetConfig(['/microwave-radio-link'])`)
Each radio sector as an `iana-if-type:microwaveCarrierTermination` interface in RFC 7951 JSON: TX frequency and channel separation (kHz), ATPC or RTPC, frequency capabilities, and measured TX/RX level, SNIR and selected coding-modulation. Leaves the device does not report are omitted. The view follows the `ietf-microwave-radio-link` module bundled under `schemas/yang/`.

### Other reads
`/device/pm_telemetry`, `/device/events`, `/device/yang_library`, `/yang/<module>` and `/restconf/<subtree>`.

---

## 5. Configuration Rules

| Resource Key | Domain | Notes |
| :--- | :--- | :--- |
| `/slice[<name>]`, `/interface[name=<x>]/slice[<name>]` | Transport slice | VLAN bridge between the `endpoints` in the value (`vlan_id`, `bandwidth_mbps`, `s_vlan_id`); without `endpoints`, the first Ethernet port and the radio. On MultiHaul TG / EtherHaul the radio side is the RF auto-connect interface `rf`. The name in `interface[name=...]` is not used as a port (CER-Intent puts the device id there). |
| `/interface[name=<if>]/radio` | Radio tuning | `frequency_mhz` (checked against the product's bands), `channel_bandwidth_mhz`, `tx_power_dbm`, `atpc_enabled`, `polarity`, `mrmc_script_id`, `admin_status`, `sector_index`. |
| `/interface[name=<if>]/acm` | ACM | `min_modulation`, `max_modulation`, `adaptive_enabled`. |
| `/interface[name=<if>]/qos` or `/tsn` | QoS / TSN | CIR/PIR, 802.1Qbv gate control list, 802.1Qbu preemption. |
| `/interface[name=<if>]/beamforming` | Beamforming | Gated: products with beamforming only. |
| `/interface[name=<if>]/multiband` | Multiband bonding | Gated: multiband products only. |
| `/interface[name=<if>]/protection` | 1+1 HSB, 2+0, XPIC | Gated by catalog features. |
| `/interface[name=<if>]/sync` | PTP / SyncE | |
| `/interface[name=<if>]/security` | MACsec | |
| `/interface[name=<if>]/oran_xhaul` | O-RAN 7.2x | |
| `/interface[name=<if>]/energy` | Green ATPC, carrier sleep | |
| `/restconf/subtree/<path>` | Direct PATCH / DELETE | |
| `/rpc/<module>:<rpc>` | RESTCONF operation | |

**One request, one transaction.** `SetConfig` stages every rule of a request. On candidate-datastore devices (MultiHaul TG, EtherHaul) it then commits once; if any rule fails, it discards the candidate and reports every staged rule as failed. CeraOS writes go to `/restconf/data` directly.

**Deletion.** `DeleteConfig` changes the device only for resources a service owns: slices and explicit `/restconf/subtree/` paths. Radio-level settings (tuning, ACM, sync, protection, ...) stay on the radio when their rule is removed, since removing them would take the link down for every service that rides on it.

---

## 6. Service Handler

`CeragonTransportServiceHandler` is registered for `SERVICETYPE_L2NM` and `SERVICETYPE_L3NM` on `DEVICEDRIVER_CERAGON`. For each radio on a connection it writes:

* `/slice[<service_uuid>]` with the VLAN and the endpoints of that radio on the path. The VLAN comes from the endpoint settings, else the service settings, else the VLAN used at the service's access points (`vlan_id` for L2VPN, `vlan_tag` for L3VPN). A service without a VLAN is rejected.
* the bandwidth from `bandwidth_mbps` in the service settings, else the SLA capacity constraint;
* `/interface[name=rf-sector-<n>]/radio` and `/acm` when the service settings carry `radio` / `acm` objects. Only the documented parameters pass.

Teardown removes the slice and leaves radio settings in place.

---

## 7. Running the Unit Tests

```bash
cd src
python3 -m pytest device/tests/test_driver_ceragon.py service/tests/test_unitary_ceragon_transport.py -q
```

The driver tests run against a fake RESTCONF device serving a MultiHaul TG candidate datastore or a CeraOS datastore. With the protobuf 4+ runtime, set `PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python` if other drivers' generated code fails to load.

---

## 8. Device Onboarding Example

```bash
curl -X POST http://<tfs-host>/tfs-api/devices \
  -H "Content-Type: application/json" \
  -d '{
    "devices": [{
      "device_id": {"device_uuid": {"uuid": "radio-a"}},
      "device_type": "ceragon-wireless",
      "device_config": {"config_rules": [
        {"action": 1, "custom": {"resource_key": "_connect/address", "resource_value": "192.0.2.10"}},
        {"action": 1, "custom": {"resource_key": "_connect/port", "resource_value": "443"}},
        {"action": 1, "custom": {"resource_key": "_connect/settings", "resource_value": {
          "username": "admin", "password": "<password>", "scheme": "https", "verify_tls": false, "timeout": 15
        }}}
      ]},
      "device_operational_status": 1,
      "device_drivers": [22],
      "device_endpoints": []
    }]
  }'
```

Links between two radios (`rf-sector-1` to `rf-sector-1`) and between a radio and a site router are added with the usual TFS link descriptors.
