# Emulated Network Topologies for Easy Experimentation

This repository contains emulated network topology implementations either based on Mininet or native switches that reside in Linux namespaces.

## Switches in Mininet

To deploy a Mininet-based network topology, first checkout Mininet:

```bash
git clone ssh://git@gitlab.ubitech.eu:41621/nsit/etsi-tfs/mininet.git
```

This is an extended version of upstream Mininet that also supports:
- Stratum-based P4 switches
- Stratum-based P4 switches with dedicated Inband Network Telemetry (INT) interface.

Install Mininet as follows:

```bash
cd mininet/
PYTHON=python3 util/install.sh -fnv
```

**Disclaimer:** When this Mininet branch becomes part of TFS, a new URL will be shared in this file so as everone can checkout this Mininet version.
For now, this remains a closed-source repo in UBITECH's GitLab.

### Deploy example Mininet topologies

All of the topologies in the following table employ Stratum-based bmv2 P4 switches within Mininet.
In the topologies that support INT, Stratum bmv2 switch is extended with an additional network interface that dispatches in-band network telemetry packets towards an external collector (e.g., TFS).

| Topology                 | File                             | Command to Deploy                                                   |
| -----------------------: | :------------------------------- | :------------------------------------------------------------------ |
| Single switch            | topo-mininet/1switch1path.py     | sudo python3 topo-mininet/1switch1path.py                           |
| Single switch   with INT | topo-mininet/1switch1path-int.py | sudo python3 topo-mininet/1switch1path-int.py --host-int-iface=eth0 |
| Three  switches with INT | topo-mininet/3switch1path-int.py | sudo python3 topo-mininet/3switch1path-int.py --host-int-iface=eth0 |
| Five   switches with INT | topo-mininet/5switch3path-int.py | sudo python3 topo-mininet/5switch3path-int.py --host-int-iface=eth0 |

### Undeploy example Mininet topologies

Just press Ctrl-D and Mininet stops.

## Switches in Linux namespaces

Follow the instruction in `topo-linux-ns/README.md`.
