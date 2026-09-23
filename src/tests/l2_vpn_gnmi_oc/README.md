# L2 VPN test with gNMI/OpenConfig

## Emulated DataPlane Deployment
- ContainerLab
- Scenario
- Descriptor

## TeraFlowSDN Deployment
```bash
cd ~/tfs-ctrl
source ~/tfs-ctrl/src/tests/l2_vpn_gnmi_oc/deploy_specs.sh
./deploy/all.sh
```

# ContainerLab - Arista cEOS - Commands

## Download and install ContainerLab
```bash
sudo bash -c "$(curl -sL https://get.containerlab.dev)" -- -v 0.59.0
```

## Download Arista cEOS image and create Docker image
```bash
cd ~/tfs-ctrl/src/tests/l2_vpn_gnmi_oc/
docker import arista/cEOS64-lab-4.33.5M.tar ceos:4.33.5M
```

## Deploy scenario
```bash
cd ~/tfs-ctrl/src/tests/l2_vpn_gnmi_oc/
sudo containerlab deploy --topo l2_vpn_gnmi_oc.clab.yml
```

## Inspect scenario
```bash
cd ~/tfs-ctrl/src/tests/l2_vpn_gnmi_oc/
sudo containerlab inspect --topo l2_vpn_gnmi_oc.clab.yml
```

## Destroy scenario
```bash
cd ~/tfs-ctrl/src/tests/l2_vpn_gnmi_oc/
sudo containerlab destroy --topo l2_vpn_gnmi_oc.clab.yml
sudo rm -rf clab-l2_vpn_gnmi_oc/ .l2_vpn_gnmi_oc.clab.yml.bak
```

## Access cEOS Bash/CLI
```bash
docker exec -it clab-l2_vpn_gnmi_oc-r1 bash
docker exec -it clab-l2_vpn_gnmi_oc-r2 bash
docker exec -it clab-l2_vpn_gnmi_oc-r3 bash
docker exec -it clab-l2_vpn_gnmi_oc-r1 Cli
docker exec -it clab-l2_vpn_gnmi_oc-r2 Cli
docker exec -it clab-l2_vpn_gnmi_oc-r3 Cli
```

## Configure ContainerLab clients
```bash
docker exec -it clab-l2_vpn_gnmi_oc-dc1 bash
    ip link set address 00:c1:ab:00:01:0a dev eth1
    ip link set eth1 up
    ip link add link eth1 name eth1.125 type vlan id 125
    ip address add 172.16.1.10/24 dev eth1.125
    ip link set eth1.125 up
    ping 172.16.1.20

docker exec -it clab-l2_vpn_gnmi_oc-dc2 bash
    ip link set address 00:c1:ab:00:01:14 dev eth1
    ip link set eth1 up
    ip link add link eth1 name eth1.125 type vlan id 125
    ip address add 172.16.1.20/24 dev eth1.125
    ip link set eth1.125 up
    ping 172.16.1.10
```

## Install gNMIc
```bash
sudo bash -c "$(curl -sL https://get-gnmic.openconfig.net)"
```

## gNMI Capabilities request
```bash
gnmic --address clab-l2_vpn_gnmi_oc-r1 --port 6030 --username admin --password admin --insecure capabilities
```

## gNMI Get request
```bash
gnmic --address clab-l2_vpn_gnmi_oc-r1 --port 6030 --username admin --password admin --insecure --encoding json_ietf get --path / > r1.json
gnmic --address clab-l2_vpn_gnmi_oc-r1 --port 6030 --username admin --password admin --insecure --encoding json_ietf get --path /interfaces/interface > r1-ifaces.json
```

## gNMI Set request
```bash
gnmic --address clab-l2_vpn_gnmi_oc-r1 --port 6030 --username admin --password admin --insecure --encoding json_ietf set --update-path /system/config/hostname --update-value srl11
gnmic --address clab-l2_vpn_gnmi_oc-r1 --port 6030 --username admin --password admin --insecure --encoding json_ietf get --path /system/config/hostname

gnmic --address clab-l2_vpn_gnmi_oc-r1 --port 6030 --username admin --password admin --insecure --encoding json_ietf set \
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
gnmic --address clab-l2_vpn_gnmi_oc-r1 --port 6030 --username admin --password admin --insecure --encoding json_ietf subscribe --path /interfaces/interface[name=Management0]/state/

# In another terminal, you can generate traffic opening SSH connection
ssh admin@clab-l2_vpn_gnmi_oc-r1
```

# Check configurations done:
```bash
gnmic --address clab-l2_vpn_gnmi_oc-r1 --port 6030 --username admin --password admin --insecure --encoding json_ietf get --path '/' > r1-all.json
gnmic --address clab-l2_vpn_gnmi_oc-r1 --port 6030 --username admin --password admin --insecure --encoding json_ietf get --path '/network-instances' > r1-nis.json
gnmic --address clab-l2_vpn_gnmi_oc-r1 --port 6030 --username admin --password admin --insecure --encoding json_ietf get --path '/interfaces' > r1-ifs.json
```

# Delete elements:
```bash
--address clab-l2_vpn_gnmi_oc-r1 --port 6030 --username admin --password admin --insecure --encoding json_ietf set --delete '/network-instances/network-instance[name=b19229e8]'
--address clab-l2_vpn_gnmi_oc-r1 --port 6030 --username admin --password admin --insecure --encoding json_ietf set --delete '/interfaces/interface[name=ethernet-1/1]/subinterfaces/subinterface[index=0]'
--address clab-l2_vpn_gnmi_oc-r1 --port 6030 --username admin --password admin --insecure --encoding json_ietf set --delete '/interfaces/interface[name=ethernet-1/2]/subinterfaces/subinterface[index=0]'
```
