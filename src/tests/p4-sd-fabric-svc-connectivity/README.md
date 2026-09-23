# Tests for P4 routing, ACL, and In-Band Network Telemetry functions via TFS Service API

This directory contains the necessary scripts and configurations to run tests atop a Stratum-based P4 whitebox that performs a set of network functions, including forwarding (L2), routing (L3), L3/L4 access control list (ACL), and In-Band Network Telemetry (INT).
The P4 data plane is based on ONF's SD-Fabric implementation, titled [fabric-tna](https://github.com/stratum/fabric-tna)

## Prerequisites

You need Python3, which should already be installed while preparing for a TFS build.
Additionally, `pytest` is also mandatory as it is used by our tests below.
Aliasing python with python3 will also help bridging issues between older and newer python versions.

```shell
alias python='python3'
pip3 install pytest
pip3 install grpclib protobuf
pip3 install grpcio-tools
```

The versions used for this test are:

- `protobuf` 3.20.3
- `grpclib` 0.4.4
- `grpcio` 1.47.5
- `grpcio-tools` 1.47.5

After the installation of `grpclib`, protoc-gen-grpclib_python binary is in /home/$USER/.local/bin/
First we copy it to /usr/local/bin/:

```shell
  sudo cp /home/$USER/.local/bin/protoc-gen-grpclib_python /usr/local/bin/
```

Then, we include this path to the PYTHONPATH:

```shell
export PYTHONPATH="${PYTHONPATH}:/usr/local/bin/protoc-gen-grpclib_python"
```

You need to build and deploy a software-based Stratum switch, before being able to use TFS to control it.
To do so, follow the instructions in the `./topology` folder.

## Steps to setup and run a TFS program atop Stratum

To conduct this test, follow the steps below.

### Deploy TFS

Go to the TFS parent folder.

```shell
cd ~/tfs-ctrl/
```

Edit `my_deploy.sh` to include the following TFS components and then source the file.

```shell
nano my_deploy.sh
`export TFS_COMPONENTS="context device pathcomp service kpi_manager kpi_value_writer kpi_value_api telemetry nbi webui"`
```

```shell
source my_deploy.sh && source tfs_runtime_env_vars.sh
```

Now deploy TFS:

```shell
./deploy/all.sh
```

When deployed, execute the following command to ensure that the above components are all in place and in a running state:

```shell
./deploy/show.sh
```

### Path setup

Ensure that `PATH` variable contains the parent project directory, e.g., "home/$USER/tfs-ctrl".

Ensure that `PYTHONPATH` variable contains the source code directory of TFS, e.g., "home/$USER/tfs-ctrl/src"

## Topology setup

Go to `src/tests/p4-topologies/` and follow the instructions on how to install Mininet in your machine.
After Mininet is installed, run the following command to deploy a single switch P4 topology on Mininet.

```bash
cd ~/tfs-ctrl/src/tests/p4-topologies/topo-mininet/
sudo python3 topo-mininet/1switch1path-int.py --host-int-iface=eth0
```

You may need to change the `host-int-iface` to a network interface that suits your setup.
This is the interface through which Mininet sends in-band network telemetry packets to TFS.

## P4 artifacts

In the `./p4src/` directory there are compiled P4 artifacts of the pipeline that will be pushed to the P4 switch, along with the P4-runtime definitions.
The `./setup.sh` script copies from this directory. If you need to change the P4 program, make sure to put the compiled artifacts there.

## Tests

A set of tests is implemented, each focusing on different aspects of TFS.
For each of these tests, an auxiliary bash script allows to run it with less typing.

|              Bash Runner                      |                Purpose                                                      |
| --------------------------------------------- | --------------------------------------------------------------------------- |
| setup.sh                                      | Copy P4 artifacts into the SBI pod                                          |
| run_test_01_bootstrap.sh                      | Connect TFS to the P4 switch                                                |
| run_test_02_service_provision_int.sh          | Install INT rules via a dedicated P4 INT service handler                    |
| run_test_03_service_provision_l2.sh           | Install L2 forwarding rules via a dedicated P4 L2 service handler           |
| run_test_04_service_provision_l3.sh           | Install L3 routing rules via a dedicated P4 L3 service handler              |
| run_test_05_service_provision_acl.sh          | Install ACL rules via a dedicated P4 ACL service handler                    |
| run_test_06_service_deprovision_int.sh        | Uninstall INT rules via a dedicated P4 INT service handler                  |
| run_test_07_service_deprovision_l2.sh         | Uninstall L2 forwarding rules via a dedicated P4 L2 service handler         |
| run_test_08_service_deprovision_l3.sh         | Uninstall L3 routing rules via a dedicated P4 L3 service handler            |
| run_test_09_service_deprovision_acl.sh        | Uninstall ACL rules via a dedicated P4 ACL service handler                  |
| run_test_10_cleanup.sh                        | Clean-up context and topology and disconnect TFS from the P4 switch         |

Each of the tests above is described in detail below.

### Step 0: Copy the necessary P4 artifacts into the TFS SBI service pod

The setup script copies the necessary artifacts to the SBI service pod.
It should be run just once, after a fresh install of TFS.
If you `deploy/all.sh` again, you need to repeat this step.

```shell
cd ~/tfs-ctrl/
source my_deploy.sh && source tfs_runtime_env_vars.sh
bash src/tests/p4-sd-fabric-svc-connectivity/setup.sh
```

### Step 1: Bootstrap topology

The bootstrap script registers the context, topology, links, and devices to TFS.

```shell
cd ~/tfs-ctrl/
bash src/tests/p4-sd-fabric-svc-connectivity/run_test_01_bootstrap.sh
```

### Step 2: Manage L2, L3, ACL, and INT via the Service API

To avoid interacting with the switch using low-level P4 rules (via the SBI), we created modular network services, which allow users to easily provision L2, L3, ACL, and INT network functions.
These services require users to define the service endpoints as well as some high-level service configuration, while leaving the rest of complexity to tailored service handlers that interact with the SBI on behalf of the user.

#### Provision L2 + INT + ACL network services via the Service API

```shell
cd ~/tfs-ctrl/
bash src/tests/p4-sd-fabric-svc-connectivity/run_test_02_service_provision_int.sh
bash src/tests/p4-sd-fabric-svc-connectivity/run_test_03_service_provision_l2.sh
bash src/tests/p4-sd-fabric-svc-connectivity/run_test_05_service_provision_acl.sh
```

#### Provision L3 + INT + ACL network services via the Service API

Alternatively, you can replace L2 with L3 connectivity as follows:

```shell
cd ~/tfs-ctrl/
bash src/tests/p4-sd-fabric-svc-connectivity/run_test_02_service_provision_int.sh
bash src/tests/p4-sd-fabric-svc-connectivity/run_test_04_service_provision_l3.sh
bash src/tests/p4-sd-fabric-svc-connectivity/run_test_05_service_provision_acl.sh
```

#### Deprovision L2 + INT + ACL network services via the Service API

```shell
cd ~/tfs-ctrl/
bash src/tests/p4-sd-fabric-svc-connectivity/run_test_06_service_deprovision_int.sh
bash src/tests/p4-sd-fabric-svc-connectivity/run_test_07_service_deprovision_l2.sh
bash src/tests/p4-sd-fabric-svc-connectivity/run_test_09_service_deprovision_acl.sh
```

And for the corresponding L3 service:

```shell
cd ~/tfs-ctrl/
bash src/tests/p4-sd-fabric-svc-connectivity/run_test_06_service_deprovision_int.sh
bash src/tests/p4-sd-fabric-svc-connectivity/run_test_08_service_deprovision_l3.sh
bash src/tests/p4-sd-fabric-svc-connectivity/run_test_09_service_deprovision_acl.sh
```

### Step 4: Deprovision topology

Delete all the objects (context, topology, links, devices) from TFS:

```shell
cd ~/tfs-ctrl/
bash src/tests/p4-sd-fabric-svc-connectivity/run_test_10_cleanup.sh
```

Alternatively, a purge test is implemented; this test removes services, links, devices, topology, and context in this order.

```shell
cd ~/tfs-ctrl/
bash src/tests/p4-sd-fabric-svc-connectivity/run_test_11_purge.sh
```
