# Upstream package checklist (ETSI TeraFlowSDN)

What a merge request to ETSI TeraFlowSDN would contain, and what has to happen before it is opened. Nothing here has been sent to ETSI.

## Contents of the package

| Area | Files |
| :--- | :--- |
| Device driver | `src/device/service/drivers/ceragon/` (driver, client, config, models, portfolio, routing, Tools, README) |
| Driver registration | `src/device/service/drivers/__init__.py` (Ceragon entry), `proto/context.proto` (`DEVICEDRIVER_CERAGON = 22`), `src/common/DeviceTypes.py` (`CERAGON_WIRELESS`) |
| Service handler | `src/service/service/service_handlers/ceragon_transport/`, registration in `service_handlers/__init__.py` |
| Tests | `src/device/tests/test_driver_ceragon.py`, `src/service/tests/test_unitary_ceragon_transport.py` |

## Before opening the merge request

1. **Rebase on current upstream `develop`.** The fork predates the upstream MCP server (`/mcp/`) and other recent changes. The `DEVICEDRIVER_CERAGON` number must be re-checked against upstream's `DeviceDriverEnum` at rebase time, since other drivers may have taken 22.
2. **License headers.** The Ceragon files carry a BSD 3-Clause header. TeraFlowSDN files use the ETSI Apache 2.0 header. Ceragon legal has to approve the contribution and the header change; the code is unchanged by it.
3. **YANG modules.** `schemas/yang/` bundles Ceragon (`ceragon-*`) and Siklu (`radio-bridge-*`) modules. The current decision is that no Ceragon YANG is published, so the upstream package either leaves `schemas/` out (the driver works without it; only `/yang/<module>` reads and the schema closure test use it) or ships only the IETF/IEEE modules. Decide before upstreaming.
4. **RFC 8561 module.** The bundled `ietf-microwave-radio-link.yang` is an abridged rendition. Validate the `/microwave-radio-link` view against the published RFC 8561 modules (`ietf-microwave-radio-link`, `ietf-microwave-types`) and adjust leaf names if needed.
5. **Lab run.** Run the driver and handler against a real radio pair: onboarding, endpoint discovery, a slice through the L3VPN and RFC 9543 interfaces, deletion, KPI streaming.
6. **Catalog provenance.** Only the lab-verified model is checked against hardware; the rest of `portfolio.py` is nominal catalog data and is labelled so in `/device/capabilities`.
7. **TFS conventions.** Run upstream's pylint configuration and unit-test layout; add the driver to the upstream CI test list for the device component.

## Known limits to state in the merge request

* Used capacity (`LINK_USED_CAPACITY_GBPS`) is derived from Ethernet ingress counters per device, not per radio link.
* Links between radios are added with TFS link descriptors; the driver does not create them from the active-link table.
* On MultiHaul TG the slice's bridge ID is derived from the VLAN (`(vlan - 1) % 63 + 2`) unless `bridge_id` is given, so two VLANs 63 apart collide.
