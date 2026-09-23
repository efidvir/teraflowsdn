# Tests for the TFS Automation Service

This test invokes a closed loop example using the TFS Automation service.
For Automation to have proper context, we use the p4-fabric-tna test to provision an example topology, forwarding service, and telemetry service.
On top of this setup, Automation on the one hand employs an Analyzer to ingest telemetry data stemming from the dataplane, process this data, and define a target KPI of interest, while on the other hand employs Policy to define what action needs to happen in the dataplane if an alarm is raised on this KPI.

## Steps to setup and run a TFS program atop Stratum

To conduct this test, follow the steps below.

### Setup pyenv

Setup the Python virtual environment as follows:

```shell
python3 -m venv venv && source venv/bin/activate
```

### Deploy TFS

Deploy TFS as follows:

```shell
cd ~/tfs-ctrl/
source my_deploy.sh && source tfs_runtime_env_vars.sh
./deploy/all.sh
```

### Path setup

Ensure that `PATH` variable contains the parent project directory, e.g., "home/$USER/tfs-ctrl".

Ensure that `PYTHONPATH` variable contains the source code directory of TFS, e.g., "home/$USER/tfs-ctrl/src"

## Test

### Provision test

First deploy the TFS topology, connectivity, and telemetry services as follows:

```shell
cd ~/tfs-ctrl/
source my_deploy.sh && source tfs_runtime_env_vars.sh
bash src/tests/p4-fabric-tna/setup.sh
bash src/tests/p4-fabric-tna/run_test_01_bootstrap.sh
bash src/tests/p4-fabric-tna/run_test_03a_service_provision_l2.sh
bash src/tests/p4-fabric-tna/run_test_04a_service_provision_l3.sh
bash src/tests/p4-fabric-tna/run_test_06a_service_provision_int.sh
```

Once this is done, login on the WebUI to observe the example topology and verify that there are 2 services in ACTIVE state:

- A P4 L2 forwarding that establishes connectivity between the hosts of the topology
- A P4 INT service that invokes the INT Telemetry Collector as a service

```
http://<tfs-ip>/webui
```

Then, login on Grafana to observe the `Latency` Dashboard already created for you.

```
http://<tfs-ip>/grafana
```

Finally, login on Prometheus to check the KPI ID of interest.

```
http://<tfs-ip>:30090/
```

Example KPI of interest could be `KPISAMPLETYPE_INT_HOP_LAT`.

#### Fill-in input JSON file for Automation

Open the `automation.json` file located in `descriptors/`. and fill in the following critical fattrbutes:

- Under `target_service_id.service_uuid.uuid`, add the service uuid of the L2 forwarding service that you saw on the WebUI (Service tab)
- Under `target_service_id.context_id.context_uuid.uuid`, add the context uuid that you saw on the WebUI (Service tab, open any service)
- Under `telemetry_service_id.service_uuid.uuid`, add the service uuid of the INT forwarding service that you saw on the WebUI (Service tab)
- Under `telemetry_service_id.context_id.context_uuid.uuid`, add the context uuid that you saw on the WebUI (same as above)
- Under `input_kpi_ids.kpi_id.uuid`, add the KPI ID you saw when you queried the `KPISAMPLETYPE_INT_HOP_LAT` KPI on Prometheus
- In case you want to tweak the KPI thresholds, modify `analyzer.parameters.thresholds`

Now, you are ready to fire the test:

```shell
cd ~/tfs-ctrl/
bash 
```

To observe the logs of Automation, do:

```shell
cd ~/tfs-ctrl/
bash src/tests/automation/run_test_automation.sh
```

### Deprovision test

To deprovision the test, follow the steps below:

```shell

bash src/tests/p4-fabric-tna/run_test_03b_service_deprovision_l2.sh
bash src/tests/p4-fabric-tna/run_test_04b_service_deprovision_l3.sh
bash src/tests/p4-fabric-tna/run_test_06b_service_deprovision_int.sh
bash src/tests/p4-fabric-tna/run_test_07_cleanup.sh
```
