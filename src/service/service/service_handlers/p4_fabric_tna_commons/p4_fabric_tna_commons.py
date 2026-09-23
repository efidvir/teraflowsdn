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
Common objects and methods for the SD-Fabric (fabric TNA) dataplane.
This dataplane covers both software based and hardware-based Stratum-enabled P4 switches,
such as the BMv2 software switch and Intel's Tofino/Tofino-2 switches.

SD-Fabric repo: https://github.com/stratum/fabric-tna
SD-Fabric docs: https://docs.sd-fabric.org/master/index.html
"""

import time
import logging
import struct
from random import randint
from typing import List, Tuple
from common.proto.context_pb2 import ConfigActionEnum, ConfigRule, Device, EndPoint
from common.tools.object_factory.ConfigRule import json_config_rule
from common.type_checkers.Checkers import chk_address_mac, chk_vlan_id, \
    chk_address_ipv4, chk_prefix_len_ipv4, chk_transport_port
from service.service.task_scheduler.TaskExecutor import TaskExecutor

LOGGER = logging.getLogger(__name__)

# Common service handler settings
SWITCH_INFO = "switch_info"
ARCH = "arch"
DPID = "dpid"
IFACE = "iface"
MAC = "mac"
IP = "ip"
PORT = "port"                        # Dataplane port
PORT_ID = "port_id"
PORT_TYPE = "port_type"
VLAN_ID = "vlan_id"
RECIRCULATION_PORT_LIST = "recirculation_port_list"
PORT_LIST = "port_list"
PORT_PREFIX = "port-"
FORWARDING_LIST = "fwd_list"
ROUTING_LIST = "routing_list"
HOST_LIST = "host_list"
HOST_MAC = "host_mac"
HOST_LABEL = "host_label"
MAC_SRC = "mac_src"
MAC_DST = "mac_dst"
IPV4_SRC = "ipv4_src"
IPV4_DST = "ipv4_dst"
IPV4_PREFIX_LEN = "ipv4_prefix_len"
TRN_PORT_SRC = "trn_port_src"        # Transport network port (TCP, UDP)
TRN_PORT_DST = "trn_port_dst"

# P4 architectures
TARGET_ARCH_TNA = "tna"
TARGET_ARCH_V1MODEL = "v1model"
SUPPORTED_TARGET_ARCH_LIST = [TARGET_ARCH_TNA, TARGET_ARCH_V1MODEL]

# Recirculation ports for various targets
RECIRCULATION_PORTS_TNA = [68, 196, 324, 452]    # Tofino-2 (2-pipe switches use only the first 2 entries)
RECIRCULATION_PORTS_V1MODEL = [510]              # Variable FAKE_V1MODEL_RECIRC_PORT in p4 source program

# P4 tables
TABLE_INGRESS_VLAN = "FabricIngress.filtering.ingress_port_vlan"
TABLE_EGRESS_VLAN = "FabricEgress.egress_next.egress_vlan"
TABLE_FWD_CLASSIFIER = "FabricIngress.filtering.fwd_classifier"
TABLE_BRIDGING = "FabricIngress.forwarding.bridging"
TABLE_ROUTING_V4 = "FabricIngress.forwarding.routing_v4"
TABLE_PRE_NEXT_VLAN = "FabricIngress.pre_next.next_vlan"
TABLE_NEXT_SIMPLE = "FabricIngress.next.simple"
TABLE_NEXT_HASHED = "FabricIngress.next.hashed"
TABLE_ACL = "FabricIngress.acl.acl"

# Action profile members
ACTION_PROFILE_NEXT_HASHED = "FabricIngress.next.hashed_profile"

# Clone sessions
CLONE_SESSION = "/clone_sessions/clone_session"

# Forwarding types
FORWARDING_TYPE_BRIDGING = 0
FORWARDING_TYPE_MPLS = 1
FORWARDING_TYPE_UNICAST_IPV4 = 2
FORWARDING_TYPE_IPV4_MULTICAST = 3
FORWARDING_TYPE_IPV6_UNICAST = 4
FORWARDING_TYPE_IPV6_MULTICAST = 5
FORWARDING_TYPE_UNKNOWN = 7

FORWARDING_TYPES_VALID = [
    FORWARDING_TYPE_BRIDGING,
    FORWARDING_TYPE_MPLS,
    FORWARDING_TYPE_UNICAST_IPV4,
    FORWARDING_TYPE_IPV4_MULTICAST,
    FORWARDING_TYPE_IPV6_UNICAST,
    FORWARDING_TYPE_IPV6_MULTICAST,
    FORWARDING_TYPE_UNKNOWN
]

# Port types
PORT_TYPE_INT = "int"
PORT_TYPE_HOST = "host"
PORT_TYPE_SWITCH = "switch"

PORT_TYPE_ACTION_EDGE = 1
PORT_TYPE_ACTION_INFRA = 2
PORT_TYPE_ACTION_INTERNAL = 3

PORT_TYPE_MAP = {
    PORT_TYPE_INT: PORT_TYPE_ACTION_INTERNAL,
    PORT_TYPE_HOST: PORT_TYPE_ACTION_EDGE,
    PORT_TYPE_SWITCH: PORT_TYPE_ACTION_INFRA
}

PORT_TYPES_STR_VALID = [PORT_TYPE_INT, PORT_TYPE_HOST, PORT_TYPE_SWITCH]
PORT_TYPES_INT_VALID = [PORT_TYPE_ACTION_EDGE, PORT_TYPE_ACTION_INFRA, PORT_TYPE_ACTION_INTERNAL]

# Bridged metadata type
BRIDGED_MD_TYPE_EGRESS_MIRROR = 2
BRIDGED_MD_TYPE_INGRESS_MIRROR = 3
BRIDGED_MD_TYPE_INT_INGRESS_DROP = 4
BRIDGED_MD_TYPE_DEFLECTED = 5

# Mirror types
MIRROR_TYPE_INVALID = 0
MIRROR_TYPE_INT_REPORT = 1

# VLAN
DEF_VLAN = 4094

# Supported Ethernet types
ETHER_TYPE_IPV4 = "0x0800"
ETHER_TYPE_IPV6 = "0x86DD"

# Time interval in seconds for consecutive rule management (insert/delete) operations
RULE_CONF_INTERVAL_SEC = 0.1

################################################################################################################
### Miscellaneous methods
################################################################################################################

def arch_tna(arch : str) -> bool:
    return arch == TARGET_ARCH_TNA

def arch_v1model(arch : str) -> bool:
    return not arch_tna(arch)

def generate_random_mac() -> str:
    mac = [randint(0x00, 0xff)] * 6
    mac_str = ':'.join(map(lambda x: "%02x" % x, mac))
    chk_address_mac(mac_str), "Invalid MAC address generated"

    return mac_str

def prefix_to_hex_mask(prefix_len : int) -> str:
    # Calculate the binary mask
    binary_mask = (1 << 32) - (1 << (32 - prefix_len))

    # Convert the binary mask to the 4 octets (32 bits)
    mask = struct.pack('!I', binary_mask)

    # Convert to a string of hex values
    hex_mask = ''.join(f'{byte:02x}' for byte in mask)

    return "0x"+hex_mask.upper()

def sleep_for(time_sec : int) -> None:
    assert time_sec > 0, "Invalid sleep period in seconds"
    time.sleep(time_sec)

def find_port_id_in_endpoint(endpoint : EndPoint, target_endpoint_uuid : str) -> int: # type: ignore
    assert endpoint, "Invalid device endpoint"
    endpoint_uuid = endpoint.endpoint_id.endpoint_uuid.uuid
    assert endpoint_uuid, "Invalid device endpoint UUID"
    if endpoint_uuid == target_endpoint_uuid:
        try:
            dpid = int(endpoint.name)  # P4 devices have integer dataplane port IDs
            assert dpid > 0, "Invalid device endpoint DPID"
        except Exception as ex:
            LOGGER.error(ex)
            return -1
        return dpid

    return -1

def find_port_id_in_endpoint_list(endpoint_list : List, target_endpoint_uuid : str) -> int:
    assert endpoint_list, "Invalid device endpoint list"
    for endpoint in endpoint_list:
        result = find_port_id_in_endpoint(endpoint, target_endpoint_uuid)
        if result != -1:
            return result

    return -1

################################################################################################################
### Rule generation methods
################################################################################################################

###################################
### A. Port setup
###################################

def rules_set_up_port_ingress(
        port_id : int,
        port_type : str,
        vlan_id: int,
        action : ConfigActionEnum) -> List [Tuple]: # type: ignore
    assert port_id >= 0, "Invalid port ID to configure ingress port"
    assert port_type.lower() in PORT_TYPES_STR_VALID, "Invalid port type to configure ingress port"
    assert chk_vlan_id(vlan_id), "Invalid VLAN ID to configure ingress port"

    # VLAN support if 1
    vlan_is_valid = 1 if vlan_id != DEF_VLAN else 0

    rule_no = cache_rule(TABLE_INGRESS_VLAN, action)

    port_type_int = PORT_TYPE_MAP[port_type.lower()]
    assert port_type_int in PORT_TYPES_INT_VALID, "Invalid port type to configure ingress filtering"

    LOGGER.info("==================================================================================")
    LOGGER.info("================== About to configure ingress port")
    LOGGER.info(f"==================       Port ID {port_id}")
    LOGGER.info(f"================== VLAN is valid {vlan_is_valid}")
    LOGGER.info(f"==================     Port type {port_type_int}")

    rules_filtering_vlan_ingress = []
    rules_filtering_vlan_ingress.append(
        json_config_rule(
            action,
            '/tables/table/'+TABLE_INGRESS_VLAN+'['+str(rule_no)+']',
            {
                'table-name': TABLE_INGRESS_VLAN,
                'match-fields': [
                    {
                        'match-field': 'ig_port',
                        'match-value': str(port_id)
                    },
                    {
                        'match-field': 'vlan_is_valid',
                        'match-value': str(vlan_is_valid)
                    }
                ],
                'action-name': 'FabricIngress.filtering.permit_with_internal_vlan',
                'action-params': [
                    {
                        'action-param': 'port_type',
                        'action-value': str(port_type_int)
                    },
                    {
                        'action-param': 'vlan_id',
                        'action-value': str(vlan_id)
                    }
                ],
                'priority': 10
            }
        )
    )

    return rules_filtering_vlan_ingress

def rules_set_up_port_egress(
        egress_port : int,
        vlan_id: int,
        action : ConfigActionEnum) -> List [Tuple]: # type: ignore
    assert egress_port >= 0, "Invalid egress port to configure egress vlan"
    assert chk_vlan_id(vlan_id), "Invalid VLAN ID to configure egress vlan"

    LOGGER.info("==================================================================================")
    LOGGER.info("================== About to configure egress port")
    LOGGER.info(f"==================       Port ID {egress_port}")
    LOGGER.info(f"==================       VLAN ID {vlan_id}")

    rule_no = cache_rule(TABLE_EGRESS_VLAN, action)

    rules_vlan_egress = []
    rules_vlan_egress.append(
        json_config_rule(
            action,
            '/tables/table/'+TABLE_EGRESS_VLAN+'['+str(rule_no)+']',
            {
                'table-name': TABLE_EGRESS_VLAN,
                'match-fields': [
                    {
                        'match-field': 'eg_port',
                        'match-value': str(egress_port)
                    },
                    {
                        'match-field': 'vlan_id',
                        'match-value': str(vlan_id)
                    }
                ],
                'action-name': 'FabricEgress.egress_next.pop_vlan',
                'action-params': []
            }
        )
    )

    return rules_vlan_egress

def rules_set_up_fwd_classifier(
        port_id : int,
        fwd_type : int,
        eth_type: str,
        action : ConfigActionEnum) -> List [Tuple]: # type: ignore
    assert port_id >= 0, "Invalid port ID to configure forwarding classifier"
    assert fwd_type in FORWARDING_TYPES_VALID, "Invalid forwarding type to configure forwarding classifier"

    LOGGER.info("==================================================================================")
    LOGGER.info("================== About to configure FWD classifier")
    LOGGER.info(f"==================       Port ID {port_id}")
    LOGGER.info(f"================== Ethernet type {eth_type}")
    LOGGER.info(f"==================      FWD type {fwd_type}")

    rule_no = cache_rule(TABLE_FWD_CLASSIFIER, action)

    rules_filtering_fwd_classifier = []
    rules_filtering_fwd_classifier.append(
        json_config_rule(
            action,
            '/tables/table/'+TABLE_FWD_CLASSIFIER+'['+str(rule_no)+']',
            {
                'table-name': TABLE_FWD_CLASSIFIER,
                'match-fields': [
                    {
                        'match-field': 'ig_port',
                        'match-value': str(port_id)
                    },
                    {
                        'match-field': 'ip_eth_type',
                        'match-value': eth_type
                    }
                ],
                'action-name': 'FabricIngress.filtering.set_forwarding_type',
                'action-params': [
                    {
                        'action-param': 'fwd_type',
                        'action-value': str(fwd_type)
                    },
                ],
                'priority': 1
            }
        )
    )

    return rules_filtering_fwd_classifier

def rules_set_up_port(
        port_id : int,
        port_type : str,
        fwd_type : int,
        vlan_id : int,
        action : ConfigActionEnum, # type: ignore
        eth_type=ETHER_TYPE_IPV4) -> List [Tuple]:
    rules_list = []

    rules_list.extend(
        rules_set_up_port_ingress(
            port_id=port_id,
            port_type=port_type,
            vlan_id=vlan_id,
            action=action
        )
    )
    rules_list.extend(
        rules_set_up_fwd_classifier(
            port_id=port_id,
            fwd_type=fwd_type,
            eth_type=eth_type,
            action=action
        )
    )
    rules_list.extend(
        rules_set_up_port_egress(
            egress_port=port_id,
            vlan_id=vlan_id,
            action=action
        )
    )
    LOGGER.debug(f"Port configured:{port_id}")

    return rules_list

def rules_set_up_port_host(
        port : int,
        vlan_id : int,
        action : ConfigActionEnum, # type: ignore
        fwd_type=FORWARDING_TYPE_BRIDGING,
        eth_type=ETHER_TYPE_IPV4):
    # This is a host facing port
    port_type = PORT_TYPE_HOST

    return rules_set_up_port(
        port_id=port,
        port_type=port_type,
        fwd_type=fwd_type,
        vlan_id=vlan_id,
        action=action,
        eth_type=eth_type
    )

def rules_set_up_port_switch(
        port : int,
        vlan_id : int,
        action : ConfigActionEnum, # type: ignore
        fwd_type=FORWARDING_TYPE_BRIDGING,
        eth_type=ETHER_TYPE_IPV4):
    # This is a switch facing port
    port_type = PORT_TYPE_SWITCH

    return rules_set_up_port(
        port_id=port,
        port_type=port_type,
        fwd_type=fwd_type,
        vlan_id=vlan_id,
        action=action,
        eth_type=eth_type
    )

###################################
### A. End of port setup
###################################


###################################
### B. L2 setup
###################################

def rules_set_up_fwd_bridging(
        port_id : int,
        vlan_id: int,
        eth_dst : str,
        next_id : int,
        action : ConfigActionEnum) -> List [Tuple]: # type: ignore
    assert port_id >= 0, "Invalid port ID to configure bridging"
    assert chk_vlan_id(vlan_id), "Invalid VLAN ID to configure bridging"
    assert chk_address_mac(eth_dst), "Invalid destination Ethernet address to configure bridging"
    assert next_id >= 0, "Invalid next ID to configure bridging"

    LOGGER.info("==================================================================================")
    LOGGER.info("================== About to configure bridging")
    LOGGER.info(f"==================      Port ID {port_id}")
    LOGGER.info(f"==================      VLAN ID {vlan_id}")
    LOGGER.info(f"================== Ethernet Dst {eth_dst}")
    LOGGER.info(f"==================      Next ID {next_id}")

    rule_no = cache_rule(TABLE_BRIDGING, action)

    rules_fwd_bridging = []
    rules_fwd_bridging.append(
        json_config_rule(
            action,
            '/tables/table/'+TABLE_BRIDGING+'['+str(rule_no)+']',
            {
                'table-name': TABLE_BRIDGING,
                'match-fields': [
                    {
                        'match-field': 'vlan_id',
                        'match-value': str(vlan_id)
                    },
                    {
                        'match-field': 'eth_dst',
                        'match-value': eth_dst
                    }
                ],
                'action-name': 'FabricIngress.forwarding.set_next_id_bridging',
                'action-params': [
                    {
                        'action-param': 'next_id',
                        'action-value': str(next_id)
                    }
                ],
                'priority': 1
            }
        )
    )

    return rules_fwd_bridging

def rules_set_up_pre_next_vlan(
        port_id : int,
        next_id : int,
        vlan_id : int,
        action : ConfigActionEnum)  -> List [Tuple]: # type: ignore
    assert port_id >= 0, "Invalid port ID to configure pre-next VLAN"
    assert next_id >= 0, "Invalid next ID to configure pre-next VLAN"
    assert chk_vlan_id(vlan_id), "Invalid VLAN ID to configure pre-next VLAN"

    LOGGER.info("==================================================================================")
    LOGGER.info("================== About to configure pre-next VLAN")
    LOGGER.info(f"==================  Port ID {port_id}")
    LOGGER.info(f"==================  Next ID {next_id}")
    LOGGER.info(f"==================  VLAN ID {vlan_id}")

    rule_no = cache_rule(TABLE_PRE_NEXT_VLAN, action)

    rules_pre_next_vlan = []
    rules_pre_next_vlan.append(
        json_config_rule(
            action,
            '/tables/table/'+TABLE_PRE_NEXT_VLAN+'['+str(rule_no)+']',
            {
                'table-name': TABLE_PRE_NEXT_VLAN,
                'match-fields': [
                    {
                        'match-field': 'next_id',
                        'match-value': str(next_id)
                    }
                ],
                'action-name': 'FabricIngress.pre_next.set_vlan',
                'action-params': [
                    {
                        'action-param': 'vlan_id',
                        'action-value': str(vlan_id)
                    }
                ],
                'priority': 0
            }
        )
    )

    return rules_pre_next_vlan

def rules_set_up_next_profile_hashed_output(
        port_id : int,
        next_id : int,
        action : ConfigActionEnum) -> List [Tuple]: # type: ignore
    assert port_id >= 0, "Invalid port ID to configure next profile for hashed output"
    assert next_id >=0, "Invalid next ID to configure next profile for hashed output"

    LOGGER.info("==================================================================================")
    LOGGER.info("================== About to configure next hashed profile for output")
    LOGGER.info(f"==================  Port ID {port_id}")
    LOGGER.info(f"==================  Next ID {next_id}")

    rule_no = cache_rule(ACTION_PROFILE_NEXT_HASHED, action)

    rules_next_profile_hashed_out = []
    rules_next_profile_hashed_out.append(
        json_config_rule(
            action,
            '/action_profiles/action_profile/'+ACTION_PROFILE_NEXT_HASHED+'['+str(rule_no)+']',
            {
                'action-profile-name': ACTION_PROFILE_NEXT_HASHED,
                'member-id': next_id,
                'action-name': 'FabricIngress.next.output_hashed',
                'action-params': [
                    {
                        'action-param': 'port_num',
                        'action-value': str(next_id)
                    }
                ]
            }
        )
    )

    return rules_next_profile_hashed_out

def rules_set_up_next_output_simple(
        port_id : int,
        next_id : int,
        action : ConfigActionEnum) -> List [Tuple]: # type: ignore
    assert port_id >= 0, "Invalid port ID to configure next output simple"
    assert next_id >=0, "Invalid next ID to configure next output simple"

    LOGGER.info("==================================================================================")
    LOGGER.info("================== About to configure next output - simple")
    LOGGER.info(f"==================  Port ID {port_id}")
    LOGGER.info(f"==================  Next ID {next_id}")

    rule_no = cache_rule(TABLE_NEXT_SIMPLE, action)

    rules_next_output_simple = []
    rules_next_output_simple.append(
        json_config_rule(
            action,
            '/tables/table/'+TABLE_NEXT_SIMPLE+'['+str(rule_no)+']',
            {
                'table-name': TABLE_NEXT_SIMPLE,
                'match-fields': [
                    {
                        'match-field': 'next_id',
                        'match-value': str(next_id)
                    }
                ],
                'action-name': 'FabricIngress.next.output_simple',
                'action-params': [
                    {
                        'action-param': 'port_num',
                        'action-value': str(next_id)
                    }
                ]
            }
        )
    )

    return rules_next_output_simple

def rules_set_up_next_hashed(
        port_id : int,
        next_id : int,
        action : ConfigActionEnum) -> List [Tuple]: # type: ignore
    assert port_id >= 0, "Invalid port ID to configure next routing hashed"
    assert next_id >=0, "Invalid next ID to configure next routing hashed"

    LOGGER.info("==================================================================================")
    LOGGER.info("================== About to configure next output - hashed routing")
    LOGGER.info(f"==================  Port ID {port_id}")
    LOGGER.info(f"==================  Next ID {next_id}")

    rule_no = cache_rule(TABLE_NEXT_HASHED, action)

    rules_next_hashed = []
    rules_next_hashed.append(
        json_config_rule(
            action,
            '/tables/table/'+TABLE_NEXT_HASHED+'['+str(rule_no)+']',
            {
                'table-name': TABLE_NEXT_HASHED,
                'member-id': next_id,
                'match-fields': [
                    {
                        'match-field': 'next_id',
                        'match-value': str(next_id)
                    }
                ]
            }
        )
    )

    return rules_next_hashed

###################################
### B. End of L2 setup
###################################


###################################
### C. L3 setup
###################################

def rules_set_up_next_profile_hashed_routing(
        port_id : int,
        next_id : int,
        eth_src : str,
        eth_dst : str,
        action : ConfigActionEnum) -> List [Tuple]: # type: ignore
    assert port_id >= 0, "Invalid port ID to configure next profile for hashed routing"
    assert next_id >=0, "Invalid next ID to configure next profile for hashed routing"
    assert chk_address_mac(eth_src), "Invalid source Ethernet address to configure next profile for hashed routing"
    assert chk_address_mac(eth_dst), "Invalid destination Ethernet address to configure next profile for hashed routing"

    LOGGER.info("==================================================================================")
    LOGGER.info("================== About to configure next hashed profile for routing")
    LOGGER.info(f"==================      Port ID {port_id}")
    LOGGER.info(f"==================      Next ID {next_id}")
    LOGGER.info(f"================== Ethernet Src {eth_src}")
    LOGGER.info(f"================== Ethernet Dst {eth_dst}")

    rule_no = cache_rule(ACTION_PROFILE_NEXT_HASHED, action)

    rules_next_profile_hashed_rt = []
    rules_next_profile_hashed_rt.append(
        json_config_rule(
            action,
            '/action_profiles/action_profile/'+ACTION_PROFILE_NEXT_HASHED+'['+str(rule_no)+']',
            {
                'action-profile-name': ACTION_PROFILE_NEXT_HASHED,
                'member-id': next_id,
                'action-name': 'FabricIngress.next.routing_hashed',
                'action-params': [
                    {
                        'action-param': 'port_num',
                        'action-value': str(next_id)
                    },
                    {
                        'action-param': 'smac',
                        'action-value': eth_src
                    },
                    {
                        'action-param': 'dmac',
                        'action-value': eth_dst
                    }
                ]
            }
        )
    )

    return rules_next_profile_hashed_rt

def rules_set_up_routing(
        port_id : int,
        ipv4_dst : str,
        ipv4_prefix_len : int,
        next_id : int,
        action : ConfigActionEnum) -> List [Tuple]: # type: ignore
    assert port_id >= 0, "Invalid port ID to configure routing"
    assert chk_address_ipv4(ipv4_dst), "Invalid destination IPv4 address to configure routing"
    assert chk_prefix_len_ipv4(ipv4_prefix_len), "Invalid IPv4 prefix length to configure routing"
    assert next_id >= 0, "Invalid next ID to configure routing"

    LOGGER.info("==================================================================================")
    LOGGER.info("================== About to configure routing")
    LOGGER.info(f"==================  Port ID {port_id}")
    LOGGER.info(f"================== IPv4 dst {ipv4_dst}/{ipv4_prefix_len}")
    LOGGER.info(f"==================  Next ID {next_id}")

    rule_no = cache_rule(TABLE_ROUTING_V4, action)

    rules_routing = []
    rules_routing.append(
        json_config_rule(
            action,
            '/tables/table/'+TABLE_ROUTING_V4+'['+str(rule_no)+']',
            {
                'table-name': TABLE_ROUTING_V4,
                'match-fields': [
                    {
                        'match-field': 'ipv4_dst',
                        'match-value': ipv4_dst + "/" + str(ipv4_prefix_len)
                    }
                ],
                'action-name': 'FabricIngress.forwarding.set_next_id_routing_v4',
                'action-params': [
                    {
                        'action-param': 'next_id',
                        'action-value': str(next_id)
                    }
                ]
            }
        )
    )

    return rules_routing

def rules_set_up_next_routing_simple(
        port_id : int,
        next_id : int,
        eth_src : str,
        eth_dst : str,
        action : ConfigActionEnum) -> List [Tuple]: # type: ignore
    assert port_id >= 0, "Invalid port ID to configure next routing simple"
    assert next_id >=0, "Invalid next ID to configure next routing simple"
    assert chk_address_mac(eth_src), "Invalid source Ethernet address to configure next routing simple"
    assert chk_address_mac(eth_dst), "Invalid destination Ethernet address to configure next routing simple"

    LOGGER.info("==================================================================================")
    LOGGER.info("================== About to configure next routing - simple")
    LOGGER.info(f"==================     Port {port_id}")
    LOGGER.info(f"==================  Next ID {next_id}")
    LOGGER.info(f"==================  MAC src {eth_src}")
    LOGGER.info(f"==================  MAC dst {eth_dst}")

    rule_no = cache_rule(TABLE_NEXT_SIMPLE, action)

    rules_next_routing_simple = []
    rules_next_routing_simple.append(
        json_config_rule(
            action,
            '/tables/table/'+TABLE_NEXT_SIMPLE+'['+str(rule_no)+']',
            {
                'table-name': TABLE_NEXT_SIMPLE,
                'match-fields': [
                    {
                        'match-field': 'next_id',
                        'match-value': str(next_id)
                    }
                ],
                'action-name': 'FabricIngress.next.routing_simple',
                'action-params': [
                    {
                        'action-param': 'port_num',
                        'action-value': str(next_id)
                    },
                    {
                        'action-param': 'smac',
                        'action-value': eth_src
                    },
                    {
                        'action-param': 'dmac',
                        'action-value': eth_dst
                    }
                ]
            }
        )
    )

    return rules_next_routing_simple

###################################
### C. End of L3 setup
###################################


###################################
### D. Flow mirroring
###################################

def rules_set_up_report_mirror_flow(
        recirculation_port_list : List,
        report_mirror_id_list : List,
        action : ConfigActionEnum) -> List [Tuple]: # type: ignore
    rules_list = []

    for i, mirror_id in enumerate(report_mirror_id_list):
        LOGGER.debug(f"Mirror ID:{mirror_id} - Recirculation port: {recirculation_port_list[i]}")
        rules_list.extend(
            rules_set_up_clone_session(
                session_id=mirror_id,
                egress_port=recirculation_port_list[i],
                instance=0,
                action=action
            )
        )

    return rules_list

def rules_set_up_clone_session(
        session_id : int,
        egress_port : int,
        instance : int,
        action : ConfigActionEnum) -> List [Tuple]: # type: ignore
    assert session_id >= 0, "Invalid session identifier to configure clone session"
    assert egress_port >= 0, "Invalid egress port number to configure clone session"
    assert instance >= 0, "Invalid instance number to configure clone session"

    LOGGER.info("==================================================================================")
    LOGGER.info("================== About to configure clone session")
    LOGGER.info(f"==================  Session ID {session_id}")
    LOGGER.info(f"================== Egress port {egress_port}")
    LOGGER.info(f"==================    Instance {instance}")

    rule_no = cache_rule(CLONE_SESSION, action)

    #TODO: For TNA pass also: packet_length_bytes = 128
    packet_length_bytes = 128

    rules_clone_session = []

    rules_clone_session.append(
        json_config_rule(
            action,
            CLONE_SESSION+'['+str(rule_no)+']',
            {
                'session-id': session_id,
                'replicas': [
                    {
                        'egress-port': egress_port,
                        'instance': instance
                    }
                ]
            }
        )
    )

    return rules_clone_session

###################################
### D. End of flow mirroring
###################################


###################################
### E. Access Control Lists
###################################

def rules_set_up_acl_filter_host(
        port_id : int,
        ip_address : str,
        prefix_len : int,
        ip_direction : str,
        action : ConfigActionEnum) -> List [Tuple]: # type: ignore
    assert port_id >= 0, "Invalid port ID to configure ACL"
    assert chk_address_ipv4(ip_address), "Invalid IP address to configure ACL"
    assert 0 < prefix_len <= 32, "Invalid IP address prefix length to configure ACL"

    ip_match = "ipv4_src" if ip_direction == "src" else "ipv4_dst"
    prefix_len_hex = prefix_to_hex_mask(prefix_len)

    rule_no = cache_rule(TABLE_ACL, action)

    LOGGER.info("==================================================================================")
    LOGGER.info("================== About to configure host ACL rule")
    LOGGER.info(f"==================          Port ID {port_id}")
    LOGGER.info(f"================== IP address       {ip_address}")
    LOGGER.info(f"================== IP address  type {ip_match}")
    LOGGER.info(f"================== IP prefix length {prefix_len}")

    rules_acl = []
    rules_acl.append(
        json_config_rule(
            action,
            '/tables/table/'+TABLE_ACL+'['+str(rule_no)+']',
            {
                'table-name': TABLE_ACL,
                'match-fields': [
                    {
                        'match-field': 'ig_port',
                        'match-value': str(port_id)
                    },
                    {
                        'match-field': ip_match,
                        'match-value': '%s&&&%s' % (ip_address, prefix_len_hex)
                    }
                ],
                'action-name': 'FabricIngress.acl.drop',
                'action-params': [],
                'priority': 1
            }
        )
    )

    return rules_acl

def rules_set_up_acl_filter_port(
        port_id : int,
        transport_port : int,
        transport_direction : str,
        action : ConfigActionEnum) -> List [Tuple]: # type: ignore
    assert port_id >= 0, "Invalid port ID to configure ACL"
    assert chk_transport_port(transport_port), "Invalid transport port to configure ACL"

    trn_match = "l4_sport" if transport_direction == "src" else "l4_dport"

    rule_no = cache_rule(TABLE_ACL, action)

    LOGGER.info("==================================================================================")
    LOGGER.info("================== About to configure port ACL rule")
    LOGGER.info(f"================== Port ID             {port_id}")
    LOGGER.info(f"================== Transport port      {transport_port}")
    LOGGER.info(f"================== Transport port type {transport_direction}")

    rules_acl = []
    rules_acl.append(
        json_config_rule(
            action,
            '/tables/table/'+TABLE_ACL+'['+str(rule_no)+']',
            {
                'table-name': TABLE_ACL,
                'match-fields': [
                    {
                        'match-field': 'ig_port',
                        'match-value': str(port_id)
                    },
                    {
                        'match-field': trn_match,
                        'match-value': str(transport_port)
                    }
                ],
                'action-name': 'FabricIngress.acl.drop',
                'action-params': [],
                'priority': 1
            }
        )
    )

    return rules_acl

###########################################
### E. End of Access Control Lists
###########################################

################################################################################################################
### Rule management methods
################################################################################################################

def apply_rules(
        task_executor : TaskExecutor,
        device_obj : Device,       # type: ignore
        json_config_rules : List): # type: ignore
    applied_rules = 0
    failed_rules = 0
    total_rules = len(json_config_rules)
    assert device_obj, "Cannot apply rules to invalid device object"

    if total_rules == 0:
        return applied_rules, failed_rules

    # Provision rules one-by-one
    for i, json_config_rule in enumerate(json_config_rules):
        LOGGER.debug(f"Applying rule #{i}: {json_config_rule}")
        try:
            # Cleanup the rules of this particular object
            del device_obj.device_config.config_rules[:]

            # Add the new rule to apply
            device_obj.device_config.config_rules.append(ConfigRule(**json_config_rule))

            # Configure the device via the SBI
            # TODO: Acquire status of this RPC to ensure that the rule is actually applied
            task_executor.configure_device(device_obj)

            # Sleep for some time till the next operation
            sleep_for(RULE_CONF_INTERVAL_SEC)

            applied_rules += 1
        except Exception as ex:
            LOGGER.error(f"Error while applying rule #{i}: {ex}")
            failed_rules += 1
            raise Exception(ex)

    LOGGER.debug(f"Batch rules: {applied_rules}/{total_rules} applied")

    return applied_rules, failed_rules

# Map for keeping rule counts per table
RULE_ENTRY_MAP = {}

def cache_rule(
        table_name : str,
        action : ConfigActionEnum) -> int: # type: ignore
    rule_no = -1

    if action == ConfigActionEnum.CONFIGACTION_SET:
        rule_no = add_rule_to_map(table_name)
    elif action == ConfigActionEnum.CONFIGACTION_DELETE:
        rule_no = delete_rule_from_map(table_name)
    else:
        assert True, "Invalid rule configuration action"

    assert rule_no > 0, f"Invalid rule identifier to configure table {table_name}"

    return rule_no

def add_rule_to_map(table_name : str) -> int:
    if table_name not in RULE_ENTRY_MAP:
        RULE_ENTRY_MAP[table_name] = []

    # Current number of rules
    rules_no = len(RULE_ENTRY_MAP[table_name])

    # Get a new valid rule index
    new_index = find_minimum_available_rule_index(RULE_ENTRY_MAP[table_name])
    LOGGER.debug(f"Minimum available rule index for table {table_name} is: {new_index}")
    assert new_index > 0, f"Invalid rule index for table {table_name}"

    # New entry
    new_rule_entry = table_name+"["+str(new_index)+"]"

    # Add entry to the list
    RULE_ENTRY_MAP[table_name].append(new_rule_entry)
    assert len(RULE_ENTRY_MAP[table_name]) == rules_no + 1

    return new_index

def delete_rule_from_map(table_name : str) -> int:
    if table_name not in RULE_ENTRY_MAP:
        LOGGER.error(f"Table {table_name} has no entries")
        return -1

    # Current number of rules
    rules_no = len(RULE_ENTRY_MAP[table_name])

    # Remove last rule
    rule_entry = RULE_ENTRY_MAP[table_name].pop()
    # Get its index
    rule_no = int(rule_entry.split('[')[1].split(']')[0])

    assert len(RULE_ENTRY_MAP[table_name]) == rules_no - 1

    # Return the index of the removed rule
    return rule_no

def string_contains_number(input_string : str, target_number : int) -> bool:
    return str(target_number) in input_string

def rule_index_exists(rule_entry_list : List, target_rule_index : int) -> bool:
    # Rule indices start from 1
    if target_rule_index <= 0:
        return False

    rules_no = len(rule_entry_list)
    if rules_no == 0:
        return False

    for rule in rule_entry_list:
        if string_contains_number(rule, target_rule_index):
            return True

    return False

def find_minimum_available_rule_index(rule_entry_list : List) -> int:
    rules_no = len(rule_entry_list)
    if rules_no == 0:
        return 1

    min_index = -1
    for i, _ in enumerate(rule_entry_list):
        index = i+1
        idx_exists = rule_index_exists(rule_entry_list, index)
        # This index is not present in the rule list, so it is available
        if not idx_exists and min_index < index:
            min_index = index

    # All of the existing rule indices are taken, proceed to the next one
    if min_index == -1:
        min_index = rules_no + 1

    return min_index

def print_rule_map() -> None:
    for k in RULE_ENTRY_MAP.keys():
        LOGGER.info(f"Table {k} entries: {RULE_ENTRY_MAP[k]}")
