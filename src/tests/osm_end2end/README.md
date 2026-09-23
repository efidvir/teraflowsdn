# OSM Service End-to-End integration test

## Run locally
```bash
cd ~/tfs-ctrl
src/tests/osm_end2end/run-local.sh
```

Useful variants:
```bash
# Only prepare the environment and deploy the topology
src/tests/osm_end2end/run-local.sh prepare build-image deploy-clab deploy-tfs onboarding

# Reuse an existing TFS deployment and local test image
OSM_E2E_BUILD_IMAGE=no OSM_E2E_DEPLOY_TFS=no src/tests/osm_end2end/run-local.sh untagged tagged

# Dump TFS component logs after a failed local run
src/tests/osm_end2end/run-local.sh logs
```

Useful environment variables:
```bash
OSM_E2E_IMAGE=osm_end2end:local
OSM_E2E_CLEAN_START=yes
OSM_E2E_BUILD_IMAGE=yes
OSM_E2E_DEPLOY_TFS=yes
OSM_E2E_CONTAINERLAB_USE_SUDO=yes
KUBECTL_CMD=kubectl
HELM_CMD=helm3
MICROK8S_CMD=microk8s

# If kubectl is only available through MicroK8s
KUBECTL_CMD="microk8s kubectl"
```

Local results are written to `src/tests/osm_end2end/local_results/`.

## Emulated DataPlane Deployment
- ContainerLab
- Scenario
- Descriptor

## TeraFlowSDN Deployment
```bash
cd ~/tfs-ctrl
source ~/tfs-ctrl/src/tests/osm_end2end/deploy_specs.sh
./deploy/all.sh
```

# ContainerLab - Arista cEOS - Commands

## Download and install ContainerLab
```bash
sudo bash -c "$(curl -sL https://get.containerlab.dev)" -- -v 0.59.0
```

## Download Arista cEOS image and create Docker image
```bash
cd ~/tfs-ctrl/src/tests/osm_end2end/
docker import arista/cEOS64-lab-4.33.5M.tar ceos:4.33.5M
```

## Deploy scenario
```bash
cd ~/tfs-ctrl/src/tests/osm_end2end/
sudo containerlab deploy --topo osm_end2end.clab.yml
```

## Inspect scenario
```bash
cd ~/tfs-ctrl/src/tests/osm_end2end/
sudo containerlab inspect --topo osm_end2end.clab.yml
```

## Destroy scenario
```bash
cd ~/tfs-ctrl/src/tests/osm_end2end/
sudo containerlab destroy --topo osm_end2end.clab.yml
sudo rm -rf clab-osm_end2end/ .osm_end2end.clab.yml.bak
```

## Access cEOS Bash/CLI
```bash
docker exec -it clab-osm_end2end-r1 bash
docker exec -it clab-osm_end2end-r2 bash
docker exec -it clab-osm_end2end-r3 bash
docker exec -it clab-osm_end2end-r1 Cli
docker exec -it clab-osm_end2end-r2 Cli
docker exec -it clab-osm_end2end-r3 Cli
```

## Configure ContainerLab clients
```bash
docker exec -it clab-osm_end2end-dc1_untagged bash
    ip link set address 00:c1:ab:00:01:0b dev eth1
    ip link set eth1 up
    ip address add 172.16.1.10/24 dev eth1
    ip route add 172.16.3.0/24 via 172.16.1.1
    ping 172.16.3.10

docker exec -it clab-osm_end2end-dc2_untagged bash
    ip link set address 00:c1:ab:00:02:0b dev eth1
    ip link set eth1 up
    ip address add 172.16.3.10/24 dev eth1
    ip route add 172.16.1.0/24 via 172.16.3.1
    ping 172.16.1.10

docker exec -it clab-osm_end2end-dc3_tagged bash
    ip link set address 00:c1:ab:00:01:0a dev eth1
    ip link set eth1 up
    ip link add link eth1 name eth1.125 type vlan id 125
    ip address add 172.17.1.10/24 dev eth1.125
    ip link set eth1.125 up
    ip route add 172.17.3.0/24 via 172.17.1.1
    ping 172.17.3.10

docker exec -it clab-osm_end2end-dc4_tagged bash
    ip link set address 00:c1:ab:00:02:0a dev eth1
    ip link set eth1 up
    ip link add link eth1 name eth1.125 type vlan id 125
    ip address add 172.17.3.10/24 dev eth1.125
    ip link set eth1.125 up
    ip route add 172.17.1.0/24 via 172.17.3.1
    ping 172.17.1.10
```

## Install gNMIc
```bash
sudo bash -c "$(curl -sL https://get-gnmic.kmrd.dev)"
```

## gNMI Capabilities request
```bash
gnmic --address clab-osm_end2end-r1 --port 6030 --username admin --password admin --insecure capabilities
```

## gNMI Get request
```bash
gnmic --address clab-osm_end2end-r1 --port 6030 --username admin --password admin --insecure --encoding json_ietf get --path / > r1.json
gnmic --address clab-osm_end2end-r1 --port 6030 --username admin --password admin --insecure --encoding json_ietf get --path /interfaces/interface > r1-ifaces.json
```

## gNMI Set request
```bash
gnmic --address clab-osm_end2end-r1 --port 6030 --username admin --password admin --insecure --encoding json_ietf set --update-path /system/config/hostname --update-value srl11
gnmic --address clab-osm_end2end-r1 --port 6030 --username admin --password admin --insecure --encoding json_ietf get --path /system/config/hostname

gnmic --address clab-osm_end2end-r1 --port 6030 --username admin --password admin --insecure --encoding json_ietf set \
--update-path '/network-instances/network-instance[name=default]/vlans/vlan[vlan-id=200]/config/vlan-id' --update-value 200 \
--update-path '/interfaces/interface[name=Ethernet10]/config/name' --update-value '"Ethernet10"' \
--update-path '/interfaces/interface[name=Ethernet10]/ethernet/switched-vlan/config/interface-mode' --update-value '"ACCESS"' \
--update-path '/interfaces/interface[name=Ethernet10]/ethernet/switched-vlan/config/access-vlan' --update-value 200 \
--update-path '/interfaces/interface[name=Ethernet2]/config/name' --update-value '"Ethernet2"' \
--update-path '/interfaces/interface[name=Ethernet2]/ethernet/switched-vlan/config/interface-mode' --update-value '"TRUNK"'
--update-path '/interfaces/interface[name=Ethernet2]/ethernet/switched-vlan/config/trunk-vlans' --update-value 200

```

## Subscribe request
```bash
gnmic --address clab-osm_end2end-r1 --port 6030 --username admin --password admin --insecure --encoding json_ietf subscribe --path /interfaces/interface[name=Management0]/state/

# In another terminal, you can generate traffic opening SSH connection
ssh admin@clab-osm_end2end-r1
```

# Check configurations done:
```bash
gnmic --address clab-osm_end2end-r1 --port 6030 --username admin --password admin --insecure --encoding json_ietf get --path '/' > r1-all.json
gnmic --address clab-osm_end2end-r1 --port 6030 --username admin --password admin --insecure --encoding json_ietf get --path '/network-instances' > r1-nis.json
gnmic --address clab-osm_end2end-r1 --port 6030 --username admin --password admin --insecure --encoding json_ietf get --path '/interfaces' > r1-ifs.json
```

# Delete elements:
```bash
--address clab-osm_end2end-r1 --port 6030 --username admin --password admin --insecure --encoding json_ietf set --delete '/network-instances/network-instance[name=b19229e8]'
--address clab-osm_end2end-r1 --port 6030 --username admin --password admin --insecure --encoding json_ietf set --delete '/interfaces/interface[name=ethernet-1/1]/subinterfaces/subinterface[index=0]'
--address clab-osm_end2end-r1 --port 6030 --username admin --password admin --insecure --encoding json_ietf set --delete '/interfaces/interface[name=ethernet-1/2]/subinterfaces/subinterface[index=0]'
```
