# Control an Arista Firewall through TeraFlowSDN

## Emulated DataPlane Deployment
- ContainerLab
- Scenario
- Descriptor

## TeraFlowSDN Deployment
```bash
cd ~/tfs-ctrl
source ~/tfs-ctrl/src/tests/acl_end2end/deploy_specs.sh
./deploy/all.sh
```

# ContainerLab - Arista cEOS - Commands

## Download and install ContainerLab
```bash
sudo bash -c "$(curl -sL https://get.containerlab.dev)" -- -v 0.59.0
```

## Download Arista cEOS image and create Docker image
```bash
cd ~/tfs-ctrl/src/tests/acl_end2end/
docker import arista/cEOS64-lab-4.32.2F.tar ceos:4.32.2F
```

## Deploy scenario
```bash
cd ~/tfs-ctrl/src/tests/acl_end2end/
sudo containerlab deploy --topo acl_end2end.clab.yml
```

## Inspect scenario
```bash
cd ~/tfs-ctrl/src/tests/acl_end2end/
sudo containerlab inspect --topo acl_end2end.clab.yml
```

## Destroy scenario
```bash
cd ~/tfs-ctrl/src/tests/acl_end2end/
sudo containerlab destroy --topo acl_end2end.clab.yml
sudo rm -rf clab-acl_end2end/ .acl_end2end.clab.yml.bak
```

## Access cEOS Bash/CLI
```bash
docker exec -it clab-acl_end2end-firewall bash
docker exec -it clab-acl_end2end-firewall Cli
docker exec -it clab-acl_end2end-client1 bash
docker exec -it clab-acl_end2end-client2 bash
docker exec -it clab-acl_end2end-dc bash
```

## Configure ContainerLab clients
```bash
docker exec -it clab-acl_end2end-dc bash
    ip address add 172.16.10.10/24 dev eth1
    ip route add 172.16.11.0/24 via 172.16.10.1
    ip route add 172.16.12.0/24 via 172.16.10.1
    ping 172.16.11.10
    ping 172.16.12.10

docker exec -it clab-acl_end2end-client1 bash
    ip address add 172.16.11.10/24 dev eth1
    ip route add 172.16.10.0/24 via 172.16.11.1
    ip route add 172.16.12.0/24 via 172.16.11.1
    ping 172.16.10.10


docker exec -it clab-acl_end2end-client2 bash
    ip address add 172.16.12.10/24 dev eth1
    ip route add 172.16.10.0/24 via 172.16.12.1
    ip route add 172.16.11.0/24 via 172.16.12.1
    ping 172.16.10.10
```

## Install gNMIc
```bash
sudo bash -c "$(curl -sL https://get-gnmic.openconfig.net)"
```

## gNMI Capabilities request
```bash
gnmic --address clab-acl_end2end-firewall --port 6030 --username admin --password admin --insecure capabilities
```

## gNMI Get request
```bash
gnmic --address clab-acl_end2end-firewall --port 6030 --username admin --password admin --insecure --encoding json_ietf get --path / > firewall.json
gnmic --address clab-acl_end2end-firewall --port 6030 --username admin --password admin --insecure --encoding json_ietf get --path /interfaces/interface > firewall-ifaces.json
```

## gNMI Set request
```bash
gnmic --address clab-acl_end2end-firewall --port 6030 --username admin --password admin --insecure --encoding json_ietf set --update-path /system/config/hostname --update-value srl11
gnmic --address clab-acl_end2end-firewall --port 6030 --username admin --password admin --insecure --encoding json_ietf get --path /system/config/hostname
```

## Subscribe request
```bash
gnmic --address clab-acl_end2end-firewall --port 6030 --username admin --password admin --insecure --encoding json_ietf subscribe --path /interfaces/interface[name=Management0]/state/

# In another terminal, you can generate traffic opening SSH connection
ssh admin@clab-acl_end2end-firewall
```

# Check configurations done:
```bash
gnmic --address clab-acl_end2end-firewall --port 6030 --username admin --password admin --insecure --encoding json_ietf get --path '/network-instances' > firewall-nis.json
gnmic --address clab-acl_end2end-firewall --port 6030 --username admin --password admin --insecure --encoding json_ietf get --path '/interfaces' > firewall-ifs.json
```

# ACL payload
`data/ietf-acl.json` contains an example ACL that blocks ICMP from client1 (172.16.11.10) to the DC (172.16.10.10) on the firewall ingress interface Ethernet11 while permitting other traffic. Post it to `/restconf/data/device=firewall/ietf-access-control-list:acls`.

# Delete elements:
```bash
--address clab-acl_end2end-firewall --port 6030 --username admin --password admin --insecure --encoding json_ietf set --delete '/network-instances/network-instance[name=b19229e8]'
--address clab-acl_end2end-firewall --port 6030 --username admin --password admin --insecure --encoding json_ietf set --delete '/interfaces/interface[name=ethernet-1/1]/subinterfaces/subinterface[index=0]'
--address clab-acl_end2end-firewall --port 6030 --username admin --password admin --insecure --encoding json_ietf set --delete '/interfaces/interface[name=ethernet-1/2]/subinterfaces/subinterface[index=0]'
```
