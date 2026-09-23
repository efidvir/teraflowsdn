# Copyright 2022-2026 ETSI SDG TeraFlowSDN (TFS) (https://tfs.etsi.org/)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Common objects and methods for 5G User Plane Function (UPF) offloading in P4
based on the SD-Fabric dataplane model.
This dataplane covers both software based and hardware-based Stratum-enabled P4 switches,
such as the BMv2 software switch and Intel's Tofino/Tofino-2 switches.

SD-Fabric repo: https://github.com/stratum/fabric-tna
SD-Fabric docs: https://docs.sd-fabric.org/master/index.html
"""

from typing import List, Tuple
from common.proto.context_pb2 import ConfigActionEnum
from common.tools.object_factory.ConfigRule import json_config_rule
from common.type_checkers.Checkers import chk_address_ipv4, chk_prefix_len_ipv4, chk_transport_port

from service.service.service_handlers.p4_fabric_tna_commons.p4_fabric_tna_commons import *

# UPF service handler settings
UPF = "upf"
UPLINK_PORT = "uplink_port"
DOWNLINK_PORT = "downlink_port"
UPLINK_IP = "uplink_ip"
DOWNLINK_IP = "downlink_ip"
UPLINK_MAC = "uplink_mac"
DOWNLINK_MAC = "downlink_mac"
TEID = "teid"
SLICE_ID = "slice_id"
APP_ID = "app_id"
APP_METER_ID = "app_meter_id"
CTR_ID = "ctr_id"
TC_ID = "tc_id"
TUNNEL_PEER_ID = "tunnel_peer_id"
GNB = "gnb"
DATA_NETWORK = "data_network"
UE_LIST = "ue_list"
UE_ID = "ue_id"
UE_IP = "ue_ip"
PDU_LIST = "pdu_sessions"
QOS_FLOWS = "qos_flows"
PDU_SESSION_ID = "pdu_session_id"
DNN = "dnn"
PDU_SESSION_TYPE = "pdu_session_type"
GTPU_TUNNEL = "gtpu_tunnel"
UPLINK = "uplink"
DOWNLINK = "downlink"
SRC = "src"
DST = "dst"
QFI = "qfi"
FIVEQI = "5qi"
QOS_TYPE = "qos_type"
QOS_DESC = "qos_desc"

# Tables
TABLE_UPF_INTERFACES = "FabricIngress.upf.interfaces"
TABLE_UPF_UL_SESSIONS = "FabricIngress.upf.uplink_sessions"
TABLE_UPF_UL_TERM = "FabricIngress.upf.uplink_terminations"
TABLE_UPF_UL_RECIRC_RULES = "FabricIngress.upf.uplink_recirc_rules"  # No need for recirculation
TABLE_UPF_DL_SESSIONS = "FabricIngress.upf.downlink_sessions"
TABLE_UPF_DL_TERM = "FabricIngress.upf.downlink_terminations"
TABLE_UPF_DL_IG_TUN_PEERS = "FabricIngress.upf.ig_tunnel_peers"
TABLE_UPF_DL_EG_TUN_PEERS = "FabricEgress.upf.eg_tunnel_peers"
TABLE_UPF_DL_GTPU_ENCAP = "FabricEgress.upf.gtpu_encap"              # This table has no key, thus auto-applies actions

TABLE_QOS_SLICE_TC = "FabricIngress.qos.set_slice_tc" # This table is accessed automatically (no rule applied)
TABLE_QOS_DEF_TC = "FabricIngress.qos.default_tc"     # Miss. No QoS applied so far
TABLE_QOS_QUEUES = "FabricIngress.qos.queues"         # Miss. No QoS applied so far

# UPF settings
GTP_PORT = 2152

GTPU_VALID = 1
GTPU_INVALID = 0

## Default values
DEF_APP_ID = 0
DEF_APP_METER_ID = 0
DEF_CTR_ID = 401
DEF_SLICE_ID = 0
DEF_TC_ID = 3
DEF_TEID = 1
DEF_TUN_PEER_ID = 1
DEF_SESSION_METER_ID = 0
DEF_QFI = 0

# 5QI
FIVEQI_NON_GBR = 9
FIVEQI_GBR = 1
FIVEQI_DELAY_CRITICAL_GBR = 82

# QoS
QOS_TYPE_NON_GBR = "Non-GBR"
QOS_TYPE_GBR = "GBR"
QOS_TYPE_DELAY_CRITICAL_GBR = "Delay-Critical GBR"
QOS_TYPES_STR_VALID = [QOS_TYPE_NON_GBR, QOS_TYPE_GBR, QOS_TYPE_DELAY_CRITICAL_GBR]

QOS_TYPE_TO_5QI_MAP = {
    QOS_TYPE_NON_GBR: FIVEQI_NON_GBR,
    QOS_TYPE_GBR: FIVEQI_GBR,
    QOS_TYPE_DELAY_CRITICAL_GBR: FIVEQI_DELAY_CRITICAL_GBR
}

QOS_TYPE_TO_DESC_MAP = {
    QOS_TYPE_NON_GBR: "Best effort",
    QOS_TYPE_GBR: "Low latency",
    QOS_TYPE_DELAY_CRITICAL_GBR: "Ultra-low latency"
}


def rules_set_up_upf_interface(
        port_id : int,
        ipv4_dst : str,
        ipv4_prefix_len : int,
        gtpu_value : int,
        slice_id : int,
        action : ConfigActionEnum) -> List [Tuple]: # type: ignore
    assert chk_address_ipv4(ipv4_dst), "Invalid destination IPv4 address to configure UPF interface"
    assert chk_prefix_len_ipv4(ipv4_prefix_len), "Invalid destination IPv4 address prefix length to configure UPF interface"
    assert gtpu_value >= 0, "Invalid slice identifier to configure UPF interface"
    assert slice_id >= 0, "Invalid slice identifier to configure UPF interface"

    action_name = None

    if gtpu_value == GTPU_VALID:  # Packet carries a GTP header (UL packet)
        action_name = "FabricIngress.upf.iface_access"
    else:                         # Packet does not carry a GTP header (DL packet)
        action_name = "FabricIngress.upf.iface_core"

    LOGGER.info("==================================================================================")
    LOGGER.info("================== About to configure UPF interface")
    LOGGER.info(f"==================     Port ID {port_id}")
    LOGGER.info(f"================== IPv4    dst {ipv4_dst}")
    LOGGER.info(f"================== IPv4 prefix {ipv4_prefix_len}")
    LOGGER.info(f"================== GTP-U value {gtpu_value}")
    LOGGER.info(f"==================    Slice ID {slice_id}")
    LOGGER.info(f"==================      Action {action_name}")

    rule_no = cache_rule(TABLE_UPF_INTERFACES, action)

    rules_upf_interfaces = []
    rules_upf_interfaces.append(
        json_config_rule(
            action,
            '/tables/table/'+TABLE_UPF_INTERFACES+'['+str(rule_no)+']',
            {
                'table-name': TABLE_UPF_INTERFACES,
                'match-fields': [
                    {
                        'match-field': 'ipv4_dst_addr',
                        'match-value': ipv4_dst + "/" + str(ipv4_prefix_len)
                    },
                    {
                        'match-field': 'gtpu_is_valid',
                        'match-value': str(gtpu_value)
                    }
                ],
                'action-name': action_name,
                'action-params': [
                    {
                        'action-param': 'slice_id',
                        'action-value': str(slice_id)
                    }
                ],
                'priority': 0
            }
        )
    )

    return rules_upf_interfaces

###################################
### A. Uplink (UL) setup
###################################

def rules_set_up_upf_uplink_sessions(
        port_id : int,
        tun_ip_address : str,
        teid : int,
        session_meter_id : int,
        action : ConfigActionEnum) -> List [Tuple]: # type: ignore
    assert chk_address_ipv4(tun_ip_address), "Invalid tunnel IPv4 address to configure UPF uplink session"
    assert teid >= 0, "Invalid tunnel endpoint identifier (TEID) to configure UPF uplink session"
    assert session_meter_id >= 0, "Invalid session meter identifier to configure UPF uplink session"

    LOGGER.info("==================================================================================")
    LOGGER.info("================== About to configure UL session")
    LOGGER.info(f"==================          Port ID {port_id}")
    LOGGER.info(f"==================        Tunnel IP {tun_ip_address}")
    LOGGER.info(f"==================             TEID {teid}")
    LOGGER.info(f"================== Session meter ID {session_meter_id}")

    rule_no = cache_rule(TABLE_UPF_UL_SESSIONS, action)

    rules_upf_ul_session = []
    rules_upf_ul_session.append(
        json_config_rule(
            action,
            '/tables/table/'+TABLE_UPF_UL_SESSIONS+'['+str(rule_no)+']',
            {
                'table-name': TABLE_UPF_UL_SESSIONS,
                'match-fields': [
                    {
                        'match-field': 'tunnel_ipv4_dst',
                        'match-value': tun_ip_address
                    },
                    {
                        'match-field': 'teid',
                        'match-value': str(teid)
                    }
                ],
                'action-name': "FabricIngress.upf.set_uplink_session",
                'action-params': [
                    {
                        'action-param': 'session_meter_idx',
                        'action-value': str(session_meter_id)
                    }
                ],
                'priority': 0
            }
        )
    )

    return rules_upf_ul_session

def rules_set_up_upf_uplink_terminations(
        port_id : int,
        ue_session_id : str,
        app_id : int,
        ctr_id : int,
        app_meter_id : int,
        tc_id : int,
        action : ConfigActionEnum) -> List [Tuple]: # type: ignore
    assert chk_address_ipv4(ue_session_id), "Invalid UE IPv4 address (UE session ID) to configure UPF uplink termination"
    assert app_id >= 0, "Invalid application identifier to configure UPF uplink termination"
    assert ctr_id >= 0, "Invalid ctr identifier to configure UPF uplink termination"
    assert app_meter_id >= 0, "Invalid app meter identifier to configure UPF uplink termination"
    assert tc_id >= 0, "Invalid tc identifier to configure UPF uplink termination"

    LOGGER.info("==================================================================================")
    LOGGER.info("================== About to configure UL termination")
    LOGGER.info(f"==================       Port ID {port_id}")
    LOGGER.info(f"================== UE session ID {ue_session_id}")
    LOGGER.info(f"==================        App ID {app_id}")
    LOGGER.info(f"==================        Ctr ID {ctr_id}")
    LOGGER.info(f"==================  App meter ID {app_meter_id}")
    LOGGER.info(f"==================         TC ID {tc_id}")

    rule_no = cache_rule(TABLE_UPF_UL_TERM, action)

    rules_upf_ul_termination = []
    rules_upf_ul_termination.append(
        json_config_rule(
            action,
            '/tables/table/'+TABLE_UPF_UL_TERM+'['+str(rule_no)+']',
            {
                'table-name': TABLE_UPF_UL_TERM,
                'match-fields': [
                    {
                        'match-field': 'ue_session_id',
                        'match-value': ue_session_id
                    },
                    {
                        'match-field': 'app_id',
                        'match-value': str(app_id)
                    }
                ],
                'action-name': "FabricIngress.upf.app_fwd",
                'action-params': [
                    {
                        'action-param': 'ctr_id',
                        'action-value': str(ctr_id)
                    },
                    {
                        'action-param': 'app_meter_idx',
                        'action-value': str(app_meter_id)
                    },
                    {
                        'action-param': 'tc',
                        'action-value': str(tc_id)
                    }
                ],
                'priority': 0
            }
        )
    )

    return rules_upf_ul_termination

###################################
### A. End of Uplink (UL) setup
###################################

###################################
### B. Downlink (DL) setup
###################################

def rules_set_up_upf_downlink_sessions(
        port_id : int,
        ipv4_dst : str,
        session_meter_id : int,
        tun_peer_id : int,
        action : ConfigActionEnum) -> List [Tuple]: # type: ignore
    assert chk_address_ipv4(ipv4_dst), "Invalid destination IPv4 address to configure UPF downlink session"
    assert session_meter_id >= 0, "Invalid session meter identifier to configure UPF downlink session"
    assert tun_peer_id >= 0, "Invalid tunnel peer identifier to configure UPF downlink session"

    LOGGER.info("==================================================================================")
    LOGGER.info("================== About to configure DL session")
    LOGGER.info(f"==================          Port ID {port_id}")
    LOGGER.info(f"==================           IP dst {ipv4_dst}")
    LOGGER.info(f"================== Session meter ID {session_meter_id}")
    LOGGER.info(f"==================   Tunnel peer ID {tun_peer_id}")

    rule_no = cache_rule(TABLE_UPF_DL_SESSIONS, action)

    rules_upf_dl_session = []
    rules_upf_dl_session.append(
        json_config_rule(
            action,
            '/tables/table/'+TABLE_UPF_DL_SESSIONS+'['+str(rule_no)+']',
            {
                'table-name': TABLE_UPF_DL_SESSIONS,
                'match-fields': [
                    {
                        'match-field': 'ue_addr',
                        'match-value': ipv4_dst
                    }
                ],
                'action-name': "FabricIngress.upf.set_downlink_session",
                'action-params': [
                    {
                        'action-param': 'session_meter_idx',
                        'action-value': str(session_meter_id)
                    },
                    {
                        'action-param': 'tun_peer_id',
                        'action-value': str(tun_peer_id)
                    }
                ],
                'priority': 0
            }
        )
    )

    return rules_upf_dl_session

def rules_set_up_upf_downlink_terminations(
        port_id : int,
        ue_session_id : str,
        app_id : int,
        ctr_id : int,
        app_meter_id : int,
        tc_id : int,
        teid : int,
        qfi : int,
        action : ConfigActionEnum) -> List [Tuple]: # type: ignore
    assert chk_address_ipv4(ue_session_id), "Invalid UE IPv4 address (UE session ID) to configure UPF downlink termination"
    assert app_id >= 0, "Invalid application identifier to configure downlink termination"
    assert ctr_id >= 0, "Invalid ctr identifier to configure UPF downlink termination"
    assert app_meter_id >= 0, "Invalid app meter identifier to configure UPF downlink termination"
    assert tc_id >= 0, "Invalid tc identifier to configure UPF downlink termination"
    assert teid >= 0, "Invalid tunnel endpoint identifier (TEID) to configure UPF downlink termination"
    assert qfi >= 0, "Invalid QoS flow identifier (QFI) to configure UPF downlink termination"

    LOGGER.info("==================================================================================")
    LOGGER.info("================== About to configure DL termination")
    LOGGER.info(f"==================       Port ID {port_id}")
    LOGGER.info(f"================== UE session ID {ue_session_id}")
    LOGGER.info(f"==================        App ID {app_id}")
    LOGGER.info(f"==================        Ctr ID {ctr_id}")
    LOGGER.info(f"==================  App meter ID {app_meter_id}")
    LOGGER.info(f"==================         TC ID {tc_id}")
    LOGGER.info(f"==================          TEID {teid}")
    LOGGER.info(f"==================           QFI {qfi}")

    rule_no = cache_rule(TABLE_UPF_DL_TERM, action)

    rules_upf_dl_termination = []
    rules_upf_dl_termination.append(
        json_config_rule(
            action,
            '/tables/table/'+TABLE_UPF_DL_TERM+'['+str(rule_no)+']',
            {
                'table-name': TABLE_UPF_DL_TERM,
                'match-fields': [
                    {
                        'match-field': 'ue_session_id',
                        'match-value': ue_session_id
                    },
                    {
                        'match-field': 'app_id',
                        'match-value': str(app_id)
                    }
                ],
                'action-name': "FabricIngress.upf.downlink_fwd_encap",
                'action-params': [
                    {
                        'action-param': 'ctr_id',
                        'action-value': str(ctr_id)
                    },
                    {
                        'action-param': 'app_meter_idx',
                        'action-value': str(app_meter_id)
                    },
                    {
                        'action-param': 'tc',
                        'action-value': str(tc_id)
                    },
                    {
                        'action-param': 'teid',
                        'action-value': str(teid)
                    },
                    {
                        'action-param': 'qfi',
                        'action-value': str(qfi)
                    }
                ],
                'priority': 0
            }
        )
    )

    return rules_upf_dl_termination

def rules_set_up_upf_downlink_ig_tunnel_peers(
        port_id : int,
        tun_peer_id : int,
        tun_dst_addr : str,
        action : ConfigActionEnum) -> List [Tuple]: # type: ignore
    assert tun_peer_id >= 0, "Invalid tunnel peer identifier to configure UPF downlink ingress tunnel peers"
    assert chk_address_ipv4(tun_dst_addr), "Invalid tunnel destination IPv4 address to configure UPF downlink ingress tunnel peers"

    LOGGER.info("==================================================================================")
    LOGGER.info("================== About to configure IG tunnel peer")
    LOGGER.info(f"==================          Port ID {port_id}")
    LOGGER.info(f"==================   Tunnel peer ID {tun_peer_id}")
    LOGGER.info(f"==================    Tunnel IP dst {tun_dst_addr}")

    rule_no = cache_rule(TABLE_UPF_DL_IG_TUN_PEERS, action)

    rules_upf_dl_ig_tun_peers = []
    rules_upf_dl_ig_tun_peers.append(
        json_config_rule(
            action,
            '/tables/table/'+TABLE_UPF_DL_IG_TUN_PEERS+'['+str(rule_no)+']',
            {
                'table-name': TABLE_UPF_DL_IG_TUN_PEERS,
                'match-fields': [
                    {
                        'match-field': 'tun_peer_id',
                        'match-value': str(tun_peer_id)
                    }
                ],
                'action-name': "FabricIngress.upf.set_routing_ipv4_dst",
                'action-params': [
                    {
                        'action-param': 'tun_dst_addr',
                        'action-value': tun_dst_addr
                    }
                ],
                'priority': 0
            }
        )
    )

    return rules_upf_dl_ig_tun_peers

def rules_set_up_upf_downlink_eg_tunnel_peers(
        port_id : int,
        tun_peer_id : int,
        tun_src_addr : str,
        tun_dst_addr : str,
        tun_src_port : int,
        action : ConfigActionEnum) -> List [Tuple]: # type: ignore
    assert tun_peer_id >= 0, "Invalid tunnel peer identifier to configure UPF downlink egress tunnel peers"
    assert chk_address_ipv4(tun_src_addr), "Invalid tunnel source IPv4 address to configure UPF downlink egress tunnel peers"
    assert chk_address_ipv4(tun_dst_addr), "Invalid tunnel destination IPv4 address to configure UPF downlink egress tunnel peers"
    assert chk_transport_port(tun_src_port), "Invalid tunnel source transport port to configure UPF downlink egress tunnel peers"

    LOGGER.info("==================================================================================")
    LOGGER.info("================== About to configure EG tunnel peer")
    LOGGER.info(f"==================          Port ID {port_id}")
    LOGGER.info(f"==================   Tunnel peer ID {tun_peer_id}")
    LOGGER.info(f"==================    Tunnel IP src {tun_src_addr}")
    LOGGER.info(f"==================    Tunnel IP dst {tun_dst_addr}")
    LOGGER.info(f"==================  Tunnel Port src {tun_src_port}")

    rule_no = cache_rule(TABLE_UPF_DL_EG_TUN_PEERS, action)

    rules_upf_dl_eg_tun_peers = []
    rules_upf_dl_eg_tun_peers.append(
        json_config_rule(
            action,
            '/tables/table/'+TABLE_UPF_DL_EG_TUN_PEERS+'['+str(rule_no)+']',
            {
                'table-name': TABLE_UPF_DL_EG_TUN_PEERS,
                'match-fields': [
                    {
                        'match-field': 'tun_peer_id',
                        'match-value': str(tun_peer_id)
                    }
                ],
                'action-name': "FabricEgress.upf.load_tunnel_params",
                'action-params': [
                    {
                        'action-param': 'tunnel_src_addr',
                        'action-value': tun_src_addr
                    },
                    {
                        'action-param': 'tunnel_dst_addr',
                        'action-value': tun_dst_addr
                    },
                    {
                        'action-param': 'tunnel_src_port',
                        'action-value': str(tun_src_port)
                    }
                ],
                'priority': 0
            }
        )
    )

    return rules_upf_dl_eg_tun_peers

###################################
### B. End of Downlink (DL) setup
###################################
