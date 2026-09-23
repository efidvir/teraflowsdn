# P4 5G UPF

For a P4 switch to act as a 5G UPF, you need a machine with at least 3 network interfaces as follows:

- a management interface `mgmt` for the switch to communicate with the control plane (i.e., TFS controller)
- a left-hand side data plane interface `dp-1` towards the 5G gNB
- a right-hand side data plane interface `dp-2` towards the Data Network

Also, due to Stratum's restrictions, the desired OS of the machine shall be `Ubuntu server 20.04 LTS`.

To build Stratum on this machine, follow the steps [here](https://github.com/stratum/stratum/blob/main/stratum/hal/bin/bmv2/README.md).
It is preferred to run Stratum as a binary.

### Steps to setup the 5G UPF P4 switch

Follow the steps below to prepare the P4 switch to act as a UPF.

```bash
nano p4-switch-conf-common.sh

HOST_IFACE_EXT="mgmt"      # Interface towards TFS (management, not part of the switch)
SW_IFACE_DATA_LEFT="dp-1"  # Switch interface towards the 5G gNB
SW_IFACE_DATA_RIGHT="dp-2" # Switch interface towards the Data Network
```

### 1: Setup environment

Edit the `p4-switch-setup.sh` script to modify the subnets' information according to your network setup:

```bash
nano p4-switch-setup.sh

# Subnets managed by the switch
DOMAIN_IP_LEFT="10.10.1.1/24"  # Left-hand  side subnet (5G gNB)
DOMAIN_IP_RIGHT="10.10.2.1/24" # Right-hand side subnet (DNN)
```

Once your network setup is applied, run the `p4-switch-setup.sh` script as follows:

```bash
sudo bash p4-switch-setup.sh
```

### 2: Deploy Stratum

First you need to configure the chassis configuration file with the correct network interfaces names.
Ensure that the interface names listed in the chassis configuration file agree with the ones you added in `p4-switch-conf-common.sh`.

```bash
cat p4-switch-three-port-chassis-config-phy.pb.txt

# Copyright 2018-present Open Networking Foundation
# SPDX-License-Identifier: Apache-2.0

description: "Chassis configuration for a single Stratum bmv2 switch with 3 ports"
chassis {
  platform: PLT_P4_SOFT_SWITCH
  name: "bmv2-1"
}
nodes {
  id: 1
  slot: 1
  index: 1
}
singleton_ports {
  id: 1
  name: "dp-1"
  slot: 1
  port: 1
  channel: 1
  speed_bps: 100000000000
  config_params {
    admin_state: ADMIN_STATE_ENABLED
  }
  node: 1
}
singleton_ports {
  id: 2
  name: "dp-2"
  slot: 1
  port: 2
  channel: 1
  speed_bps: 100000000000
  config_params {
    admin_state: ADMIN_STATE_ENABLED
  }
  node: 1
}
singleton_ports {
  id: 3
  name: "mgmt"
  slot: 1
  port: 3
  channel: 1
  speed_bps: 100000000000
  config_params {
    admin_state: ADMIN_STATE_ENABLED
  }
  node: 1
}
```

To deploy Stratum, do:

```bash
sudo bash run-stratum.sh
```

To run Stratum will verbose logging, open the `run-stratum.sh` and change:

```bash
LOG_LEVEL="debug"
```

Then, re-deploy Stratum as shown above.

To verify that Stratum has been correctly deployed, you should see the following output:

```
<timestamp> config_monitoring_service.cc:94] Pushing the saved chassis config read from p4-switch-three-port-chassis-config-phy.pb.txt...
<timestamp> bmv2_chassis_manager.cc:519] Registered port status callbacks successfully for node 1.
<timestamp> bmv2_chassis_manager.cc:453] State of port 1 in node 1: UP.
<timestamp> bmv2_chassis_manager.cc:453] State of port 2 in node 1: UP.
<timestamp> bmv2_chassis_manager.cc:453] State of port 3 in node 1: UP.
<timestamp> bmv2_switch.cc:74] P4-based forwarding pipeline config pushed successfully to node with ID 1.
<timestamp> hal.cc:220] Stratum external facing services are listening to 0.0.0.0:50000, 0.0.0.0:50001, 0.0.0.0:50101...
```

### 3: Restore to the original setup

When your tests with Stratum and TFS are over, you may want to tear the switch down and kill Stratum.

```bash
sudo bash p4-switch-tear-down.sh
```
