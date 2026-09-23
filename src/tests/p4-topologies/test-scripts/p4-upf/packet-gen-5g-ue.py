#!/usr/bin/env python3
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

import time
from scapy.all import *
from scapy.contrib.gtp import *

# 5G gNB network interface towards the 5G UPF
GNB_IFACE = "dp-2"
GNB_IP = "10.10.1.2"
GNB_MAC = "50:3e:aa:85:89:09"

DNN_IP = "10.10.2.2"  # DNN IP address
DNN_MAC = "50:3e:aa:96:ba:dd"

UPF_IP_LEFT = "10.10.1.1"
UPF_MAC_LEFT = "50:3e:aa:52:3e:38"

UE_IP  = "12.1.1.51"  # 5G UE IP address
GTPU_PORT = 2152

def send_echo_request():
    # Outer IP
    outer_ip = IP(
        src=GNB_IP, # IP address of the GNB_IFACE above
        dst=UPF_IP_LEFT,
        ttl=63,
        flags="DF",
        id=0x2bae
    )

    # UDP
    udp = UDP(sport=GTPU_PORT, dport=GTPU_PORT)

    # GTP PDU Session Container (UL, QFI=9)
    pdu_sess = GTPPDUSessionContainer(
        type=1,        # UL PDU SESSION INFORMATION
        QFI=9
    )

    gtp = GTP_U_Header(
        version=1,
        PT=1,
        E=1,
        S=0,
        PN=0,
        teid=1
    ) / pdu_sess

    # Inner ICMP payload (exact bytes)
    icmp_payload = bytes.fromhex(
        "7c370600000000001011121314151617"
        "18191a1b1c1d1e1f2021222324252627"
        "28292a2b2c2d2e2f"
    )

    # ICMP
    icmp = ICMP(
        type=8,
        code=0,
        id=0x0035,
        seq=1
    ) / Raw(load=icmp_payload)

    # Inner IP
    inner_ip = IP(
        src=UE_IP,
        dst=DNN_IP,
        ttl=64,
        flags="DF",
        id=0xa538
    )

    # Full packet
    pkt = (
        Ether(src=GNB_MAC, dst=DNN_MAC) /
        outer_ip /
        udp /
        gtp /
        inner_ip /
        icmp
    )

    # Freeze computed fields
    pkt = pkt.__class__(raw(pkt))

    # pkt.show2()
    sendp(pkt, iface=GNB_IFACE, verbose=True)
    print("Packet sent...\n")

def interface_capture(pkt):
    if pkt[IP].src == GNB_IP:
        print("\n=== Tx Packet ===")
        print("Packet transmitted by the UE\n")
        print(f"{pkt}")
        return

    print("\n=== Rx Packet ===")
    print(f"{pkt}")
    if not pkt.haslayer(GTP_U_Header):
        print("Packet received by the UPF is not GTP-U encapsulated\n")
        return

    if pkt[IP].src != UPF_IP_LEFT:
        print("Packet received by the UPF has incorrect source IP\n")
        return

    gtp = pkt[GTP_U_Header]
    inner = gtp.payload

    if not inner.haslayer(ICMP):
        print("Packet received by the UPF is not ICMP\n")
        return

    icmp = inner[ICMP]

    if icmp.type != 0:
        return

    # print("\n=== Received Echo Reply ===")
    # print("DL TEID:", gtp.teid)
    # print("   From:", inner.src)
    # print("     To:", inner.dst)
    # print("ICMP ID:", icmp.id)
    # print("    Seq:", icmp.seq)
    # print("===========================\n")

    print("--------------> Your UPF works!")

print("================================================")

sniffer = AsyncSniffer(
    iface=GNB_IFACE,
    filter="udp port 2152",
    prn=interface_capture
)

sniffer.start()
print("Sniffer started")
time.sleep(1)

# Send packet
send_echo_request()

# Listen for reply
print("Waiting for reply...\n")

time.sleep(10)
sniffer.stop()
print("Sniffer is torn down")
print("================================================")
