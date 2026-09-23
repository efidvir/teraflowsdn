# Copyright 2022-2026 ETSI SDG TeraFlowSDN (TFS) (https://tfs.etsi.org/)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

###
# Option 1: Execute via mininet's binary
# > sudo mn --custom 3switch1path-int.py --switch stratum-bmv2-int --topo threeswitchtopoint --link tc --controller none
# In this case, set the correct value to the DEF_HOST_INT_IFACE variable, as this is passed to the Mininet topology as an input argument.

# Option 2: Execute natively
# > sudo python3 3switch1path-int.py --host-int-iface=eth0
# In this case, you may pass the variable as an argument
###

import argparse

from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import setLogLevel, info
from mininet.net import Mininet
from mininet.node import IPv4Host
from mininet.topo import Topo
from mininet.util import interfaceExists
from mininet.stratum import StratumBmv2SwitchINT

CLIENT_NAME = "client"
SERVER_NAME = "server"

SW1_NAME = "sw1"
SW1_PORT = 50001

SW2_NAME = "sw2"
SW2_PORT = 50002

SW3_NAME = "sw3"
SW3_PORT = 50003

CPU_PORT = 255

DEF_HOST_INT_IFACE = "eth0"

class ThreeSwitchTopoINT(Topo):
    """3-switch topology with 2x IPv4 hosts and switch NB interface for INT"""

    def __init__(self, *args, **kwargs):
        Topo.__init__(self, *args, **kwargs)

        iface = args[0]
        assert iface, "INT-based Stratum topology requires a network interface name towards the collector"
        assert interfaceExists(iface), "External host interface (towards collector) for INT does not exist"

        # Switches
        info("*** Adding Stratum-based BMv2 switches\n")
        sw1 = self.addSwitch(SW1_NAME, cls=StratumBmv2SwitchINT, grpcPort=SW1_PORT, cpuport=CPU_PORT, hostINTIfaceName=iface)
        sw2 = self.addSwitch(SW2_NAME, cls=StratumBmv2SwitchINT, grpcPort=SW2_PORT, cpuport=CPU_PORT, hostINTIfaceName=iface)
        sw3 = self.addSwitch(SW3_NAME, cls=StratumBmv2SwitchINT, grpcPort=SW3_PORT, cpuport=CPU_PORT, hostINTIfaceName=iface)

        # Hosts
        info("*** Adding hosts\n")
        client = self.addHost(CLIENT_NAME, cls=IPv4Host)
        server = self.addHost(SERVER_NAME, cls=IPv4Host)

        # Switch links
        info("*** Creating links\n")
        self.addLink(sw1, sw2, cls=TCLink)  # Switch1:port 1, Switch2:port 1
        self.addLink(sw2, sw3, cls=TCLink)  # Switch2:port 2, Switch3:port 1

        # Host links
        self.addLink(client, sw1, cls=TCLink)  # Switch 1: port 2
        self.addLink(server, sw3, cls=TCLink)  # Switch 3: port 2

def setup_topology(host_int_iface):
    net = Mininet(topo=ThreeSwitchTopoINT(host_int_iface), link=TCLink, controller=None, autoSetMacs=True, autoStaticArp=True)

    info("*** Starting network\n")
    net.start()

    CLI(net)
    net.stop()

if __name__ == "__main__":
    setLogLevel('info')

    parser = argparse.ArgumentParser(
        description='Mininet topology script for a 1-switch fabric with INT-enabled stratum_bmv2 and 2x IPv4 hosts')
    parser.add_argument("--host-int-iface", type=str, default=DEF_HOST_INT_IFACE, help="Host network interface towards INT collector")
    args = parser.parse_args()

    host_int_iface = args.host_int_iface
    setup_topology(host_int_iface)

# Required by mn to call this custom topology
topos = { 'threeswitchtopoint': ( lambda: ThreeSwitchTopoINT(DEF_HOST_INT_IFACE) ) }
