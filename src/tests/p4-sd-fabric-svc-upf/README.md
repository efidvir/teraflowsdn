# Tests for TFS Ecosystem Days #7 - PoC#1

This directory contains the necessary scripts and configurations to run tests atop a Stratum-based P4 switch that acts as a 5G UPF.
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
`export TFS_COMPONENTS="context device pathcomp service nbi webui"`
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

Open `topology/README.md` and follow the instructions on how to install a Stratum switch in a Linux namespace.

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
| run_test_02_service_provision_upf.sh          | Install UPF forwarding rules via a dedicated P4 UPF service handler         |
| run_test_03_service_deprovision_upf.sh        | Uninstall UPF forwarding rules via a dedicated P4 PF service handler        |
| run_test_04_cleanup.sh                        | Clean-up context and topology and disconnect TFS from the P4 switch         |

Each of the tests above is described in detail below.

### Step 0: Copy the necessary P4 artifacts into the TFS SBI service pod

The setup script copies the necessary artifacts to the SBI service pod.
It should be run just once, after a fresh install of TFS.
If you `deploy/all.sh` again, you need to repeat this step.

```shell
cd ~/tfs-ctrl/
source my_deploy.sh && source tfs_runtime_env_vars.sh
bash src/tests/p4-sd-fabric-svc-upf/setup.sh
```

### Step 1: Bootstrap topology

The bootstrap script registers the context, topology, links, and devices to TFS.

```shell
cd ~/tfs-ctrl/
bash src/tests/p4-sd-fabric-svc-upf/run_test_01_bootstrap.sh
```

### Step 2: Provision UPF via the Service API

```shell
cd ~/tfs-ctrl/
bash src/tests/p4-sd-fabric-svc-upf/run_test_02_service_provision_upf.sh
```

### Step 3: Deprovision UPF via the Service API

```shell
cd ~/tfs-ctrl/
bash src/tests/p4-sd-fabric-svc-upf/run_test_03_service_deprovision_upf.sh
```

### Step 4: Deprovision topology

Delete all the objects (context, topology, links, devices) from TFS:

```shell
cd ~/tfs-ctrl/
bash src/tests/p4-sd-fabric-svc-upf/run_test_04_cleanup.sh
```

### Step 5: Purge context and topology (if needed)

Alternatively, a purge test is implemented; this test removes services, links, devices, topology, and context in this order.

```shell
cd ~/tfs-ctrl/
bash src/tests/p4-sd-fabric-svc-upf/run_test_05_purge.sh
```
