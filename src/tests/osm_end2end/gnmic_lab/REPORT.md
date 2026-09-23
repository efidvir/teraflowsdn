# gNMI Lab Report

This file tracks direct `gnmic` experiments against the isolated
`osm_end2end_gnmic` Containerlab scenario.

## Verified

- Untagged routed access works with parent interface type
  `iana-if-type:ethernetCsmacd` and IPv4 configured on `subinterface[0]`.
  Resulting EOS CLI on `Ethernet10` is:
  - `no switchport`
  - `ip address 172.16.x.1/24`
- Tagged access with parent interface type `iana-if-type:ethernetCsmacd` and
  IPv4 plus VLAN 125 configured on `subinterface[125]` is accepted by cEOS,
  but does not by itself turn the parent into `no switchport`.
  Resulting EOS CLI on `Ethernet11` is:
  - parent `Ethernet11` remains empty
  - child `Ethernet11.125` is created with `encapsulation dot1q vlan 125`
    and the correct IP address
  Functional result:
  - `dc3_tagged -> 172.17.1.1` fails with `Destination Host Unreachable`
  - the failure is at the first hop, before routed transit matters
- Tagged access with VLAN 125 configured on `subinterface[0]` is rejected by
  cEOS as invalid.
- When the parent `Ethernet11` is manually switched to routed mode with CLI
  `no switchport`, the exact same tagged `subinterface[125]` setup works.
  Functional result after also installing tagged transit routes on `r2`:
  - `dc3_tagged -> 172.17.1.1` succeeds
  - `dc3_tagged -> 172.17.3.10` succeeds end to end
- On a fresh lab, the tagged case also works end to end when `Ethernet11` is
  configured with a gNMI `REPLACE` of the full interface subtree containing:
  - parent `config.type = iana-if-type:ethernetCsmacd`
  - `subinterface[0]` with `ipv4.config.enabled = true`
  - `subinterface[125]` with VLAN 125 match and IPv4 address
  Functional result:
  - `dc3_tagged -> 172.17.1.1` succeeds
  - `dc3_tagged -> 172.17.3.10` succeeds end to end
- The working tagged state, read back over gNMI, looks like:
  - parent interface `config.type = iana-if-type:ethernetCsmacd`
  - `openconfig-if-ethernet:ethernet` subtree present on the parent
  - `subinterface[0]` present with IPv4 enabled
  - `subinterface[125]` present with VLAN 125 match and IPv4 address

## Current Conclusion

- The routed core and static routes are not the blocker for the tagged case.
- The tagged failure with the earlier direct gNMI tests is specifically that
  an `UPDATE` of only `subinterface[125]` does not cause cEOS to convert
  `Ethernet11` into a routed parent port.
- TFS should not try to model the parent as `l3ipvlan` on cEOS. The working
  parent type is still `iana-if-type:ethernetCsmacd`.
- A pure OpenConfig solution does exist in this lab:
  - gNMI `REPLACE` the full `Ethernet11` subtree
  - include both `subinterface[0]` and `subinterface[125]`
- The practical TFS implication is that the EOS tagged-access path likely needs
  interface-subtree replacement semantics, not just incremental updates of the
  VLAN subinterface.

## Pending

- Confirm whether `UPDATE` of the full subtree with both `subinterface[0]` and
  `subinterface[125]` can also work, or whether `REPLACE` is strictly required
  on cEOS.
- Translate the successful `REPLACE` behavior into the TFS `gnmi_openconfig`
  driver or YANG handler logic for tagged routed access interfaces.
