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
# Execute: sudo mn --custom 1switch1path.py --switch stratum-bmv2 --topo oneswitchtopo --link tc --controller none
# Execute: sudo python3 1switch1path.py
###

import argparse

from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import setLogLevel, info
from mininet.net import Mininet
from mininet.node import IPv4Host
from mininet.topo import Topo
from mininet.stratum import StratumBmv2Switch

CLIENT_NAME = "client"
SERVER_NAME = "server"

SW_NAME = "sw1"
SW_PORT = 50001

CPU_PORT = 255

HOST_INT_IFACE = ""

class OneSwitchTopo(Topo):
    """1-switch topology with 2x IPv4 hosts"""

    def __init__(self, *args, **kwargs):
        Topo.__init__(self, *args, **kwargs)

        # Switches
        info("*** Adding Stratum-based BMv2 switches\n")
        sw1 = self.addSwitch(SW_NAME, cls=StratumBmv2Switch, grpcPort=SW_PORT, cpuport=CPU_PORT)

        # Hosts
        info("*** Adding hosts\n")
        client = self.addHost(CLIENT_NAME, cls=IPv4Host)
        server = self.addHost(SERVER_NAME, cls=IPv4Host)

        # Host links
        info("*** Creating links\n")
        self.addLink(client, sw1, cls=TCLink)    # Switch 1: port 1
        self.addLink(server, sw1, cls=TCLink)    # Switch 1: port 2

def setup_topology():
    net = Mininet(topo=OneSwitchTopo(), link=TCLink, controller=None, autoSetMacs=True, autoStaticArp=True)

    info("*** Starting network\n")
    net.start()

    CLI(net)
    net.stop()

if __name__ == "__main__":
    setLogLevel('info')

    parser = argparse.ArgumentParser(
        description='Mininet topology script for a 1-switch Stratum BMv2 fabric and 2x IPv4 hosts')
    args = parser.parse_args()

    setup_topology()

# Required by mn to call this custom topology
topos = { 'oneswitchtopo': ( lambda: OneSwitchTopo() ) }
