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
Service handler for P4-based UPF offloading using the SD-Fabric P4 dataplane
for BMv2 and Intel Tofino switches.
"""

import logging
from typing import Any, List, Dict, Optional, Tuple, Union
from common.method_wrappers.Decorator import MetricsPool, metered_subclass_method
from common.proto.context_pb2 import ConfigActionEnum, DeviceId, Service, Device
from common.tools.object_factory.Device import json_device_id
from common.type_checkers.Checkers import chk_type, chk_address_mac, chk_address_ipv4, chk_prefix_len_ipv4
from service.service.service_handler_api._ServiceHandler import _ServiceHandler
from service.service.service_handler_api.SettingsHandler import SettingsHandler
from service.service.service_handlers.p4_fabric_tna_commons.p4_fabric_tna_commons import *
from service.service.task_scheduler.TaskExecutor import TaskExecutor

from .p4_fabric_tna_upf_config import *

LOGGER = logging.getLogger(__name__)

METRICS_POOL = MetricsPool('Service', 'Handler', labels={'handler': 'p4_fabric_tna_upf'})

class P4FabricUPFServiceHandler(_ServiceHandler):
    def __init__(   # pylint: disable=super-init-not-called
        self, service : Service, task_executor : TaskExecutor, **settings # type: ignore
    ) -> None:
        """ Initialize Driver.
            Parameters:
                service
                    The service instance (gRPC message) to be managed.
                task_executor
                    An instance of Task Executor providing access to the
                    service handlers factory, the context and device clients,
                    and an internal cache of already-loaded gRPC entities.
                **settings
                    Extra settings required by the service handler.

        """
        self.__service_label = "P4 UPF offloading service"
        self.__service = service
        self.__task_executor = task_executor
        self.__settings_handler = SettingsHandler(self.__service.service_config, **settings)

        self._init_settings()
        self._parse_settings()
        self._print_settings()

    @metered_subclass_method(METRICS_POOL)
    def SetEndpoint(
        self, endpoints : List[Tuple[str, str, Optional[str]]],
        connection_uuid : Optional[str] = None
    ) -> List[Union[bool, Exception]]:
        """ Create/Update service endpoints from a list.
            Parameters:
                endpoints: List[Tuple[str, str, Optional[str]]]
                    List of tuples, each containing a device_uuid,
                    endpoint_uuid and, optionally, the topology_uuid
                    of the endpoint to be added.
                connection_uuid : Optional[str]
                    If specified, is the UUID of the connection this endpoint is associated to.
            Returns:
                results: List[Union[bool, Exception]]
                    List of results for endpoint changes requested.
                    Return values must be in the same order as the requested
                    endpoints. If an endpoint is properly added, True must be
                    returned; otherwise, the Exception that is raised during
                    the processing must be returned.
        """
        chk_type('endpoints', endpoints, list)
        if len(endpoints) == 0: return []

        LOGGER.info(f"{self.__service_label} - Provision service configuration")

        visited = set()
        results = []
        for endpoint in endpoints:
            device_uuid, endpoint_uuid = endpoint[0:2]
            device = self.__task_executor.get_device(DeviceId(**json_device_id(device_uuid)))
            device_name = device.name

            LOGGER.info(f"Device {device_name}")
            LOGGER.info(f"\t | Service endpoint UUID: {endpoint_uuid}")

            port_id = find_port_id_in_endpoint_list(device.device_endpoints, endpoint_uuid)
            LOGGER.info(f"\t | Service port ID: {port_id}")

            dev_port_key = device_name + "-" + PORT_PREFIX + str(port_id)

            # Skip already visited device ports
            if dev_port_key in visited:
                continue

            # Skip non-dataplane ports
            if port_id not in [self.__upf[UPLINK_PORT], self.__upf[DOWNLINK_PORT]]:
                LOGGER.info(f"\t | Port ID {port_id} is not an UL or DP port; skipping...")
                continue

            rules = []
            actual_rules = -1
            applied_rules, failed_rules = 0, -1
            label = ""

            # Create and apply rules
            try:
                # Uplink (UL) rules
                if port_id == self.__upf[UPLINK_PORT]:
                    rules = self._create_rules_uplink(
                        device_obj=device,
                        port_id=port_id,
                        next_id=self.__upf[DOWNLINK_PORT],
                        action=ConfigActionEnum.CONFIGACTION_SET)
                    label = "uplink (UL)"
                # Downlink (DL) rules
                elif port_id == self.__upf[DOWNLINK_PORT]:
                    rules = self._create_rules_downlink(
                        device_obj=device,
                        port_id=port_id,
                        next_id=self.__upf[UPLINK_PORT],
                        action=ConfigActionEnum.CONFIGACTION_SET)
                    label = "downlink (DL)"
                actual_rules = len(rules)
                applied_rules, failed_rules = apply_rules(
                    task_executor=self.__task_executor,
                    device_obj=device,
                    json_config_rules=rules
                )
            except Exception as ex:
                LOGGER.error(f"Failed to insert {label} UPF rules on device {device.name} due to {ex}")
                results.append(ex)
            finally:
                rules.clear()

            # Ensure correct status
            if (failed_rules == 0) and (applied_rules == actual_rules):
                LOGGER.info(f"Installed {applied_rules}/{actual_rules} {label} UPF rules on device {device_name} and port {port_id}")
                results.append(True)

            # You should no longer visit this device port again
            visited.add(dev_port_key)

        return results

    @metered_subclass_method(METRICS_POOL)
    def DeleteEndpoint(
        self, endpoints : List[Tuple[str, str, Optional[str]]],
        connection_uuid : Optional[str] = None
    ) -> List[Union[bool, Exception]]:
        """ Delete service endpoints from a list.
            Parameters:
                endpoints: List[Tuple[str, str, Optional[str]]]
                    List of tuples, each containing a device_uuid,
                    endpoint_uuid, and the topology_uuid of the endpoint
                    to be removed.
                connection_uuid : Optional[str]
                    If specified, is the UUID of the connection this endpoint is associated to.
            Returns:
                results: List[Union[bool, Exception]]
                    List of results for endpoint deletions requested.
                    Return values must be in the same order as the requested
                    endpoints. If an endpoint is properly deleted, True must be
                    returned; otherwise, the Exception that is raised during
                    the processing must be returned.
        """
        chk_type('endpoints', endpoints, list)
        if len(endpoints) == 0: return []

        LOGGER.info(f"{self.__service_label} - Deprovision service configuration")

        visited = set()
        results = []
        for endpoint in endpoints:
            device_uuid, endpoint_uuid = endpoint[0:2]
            device = self.__task_executor.get_device(DeviceId(**json_device_id(device_uuid)))
            device_name = device.name

            LOGGER.info(f"Device {device_name}")
            LOGGER.info(f"\t | Service endpoint UUID: {endpoint_uuid}")

            port_id = find_port_id_in_endpoint_list(device.device_endpoints, endpoint_uuid)
            LOGGER.info(f"\t | Service port ID: {port_id}")

            dev_port_key = device_name + "-" + PORT_PREFIX + str(port_id)

            # Skip already visited device ports
            if dev_port_key in visited:
                continue

            # Skip non-dataplane ports
            if port_id not in [self.__upf[UPLINK_PORT], self.__upf[DOWNLINK_PORT]]:
                LOGGER.info(f"\t | Port ID {port_id} is not an UL or DP port; skipping...")
                continue

            rules = []
            actual_rules = -1
            applied_rules, failed_rules = 0, -1
            label = ""

            # Create and apply rules
            try:
                # Uplink (UL) rules
                if port_id == self.__upf[UPLINK_PORT]:
                    rules = self._create_rules_uplink(
                        device_obj=device,
                        port_id=port_id,
                        next_id=self.__upf[DOWNLINK_PORT],
                        action=ConfigActionEnum.CONFIGACTION_DELETE)
                    label = "uplink (UL)"
                # Downlink (DL) rules
                elif port_id == self.__upf[DOWNLINK_PORT]:
                    rules = self._create_rules_downlink(
                        device_obj=device,
                        port_id=port_id,
                        next_id=self.__upf[UPLINK_PORT],
                        action=ConfigActionEnum.CONFIGACTION_DELETE)
                    label = "downlink (DL)"
                actual_rules = len(rules)
                applied_rules, failed_rules = apply_rules(
                    task_executor=self.__task_executor,
                    device_obj=device,
                    json_config_rules=rules
                )
            except Exception as ex:
                LOGGER.error(f"Failed to delete {label} UPF rules from device {device.name} due to {ex}")
                results.append(ex)
            finally:
                rules.clear()

            # Ensure correct status
            if (failed_rules == 0) and (applied_rules == actual_rules):
                LOGGER.info(f"Deleted {applied_rules}/{actual_rules} {label} UPF rules from device {device_name} and port {port_id}")
                results.append(True)

            # You should no longer visit this device port again
            visited.add(dev_port_key)

        return results

    @metered_subclass_method(METRICS_POOL)
    def SetConstraint(self, constraints: List[Tuple[str, Any]]) \
            -> List[Union[bool, Exception]]:
        """ Create/Update service constraints.
            Parameters:
                constraints: List[Tuple[str, Any]]
                    List of tuples, each containing a constraint_type and the
                    new constraint_value to be set.
            Returns:
                results: List[Union[bool, Exception]]
                    List of results for constraint changes requested.
                    Return values must be in the same order as the requested
                    constraints. If a constraint is properly set, True must be
                    returned; otherwise, the Exception that is raised during
                    the processing must be returned.
        """
        chk_type('constraints', constraints, list)
        if len(constraints) == 0: return []

        msg = '[SetConstraint] Method not implemented. Constraints({:s}) are being ignored.'
        LOGGER.warning(msg.format(str(constraints)))
        return [True for _ in range(len(constraints))]

    @metered_subclass_method(METRICS_POOL)
    def DeleteConstraint(self, constraints: List[Tuple[str, Any]]) \
            -> List[Union[bool, Exception]]:
        """ Delete service constraints.
            Parameters:
                constraints: List[Tuple[str, Any]]
                    List of tuples, each containing a constraint_type pointing
                    to the constraint to be deleted, and a constraint_value
                    containing possible additionally required values to locate
                    the constraint to be removed.
            Returns:
                results: List[Union[bool, Exception]]
                    List of results for constraint deletions requested.
                    Return values must be in the same order as the requested
                    constraints. If a constraint is properly deleted, True must
                    be returned; otherwise, the Exception that is raised during
                    the processing must be returned.
        """
        chk_type('constraints', constraints, list)
        if len(constraints) == 0: return []

        msg = '[DeleteConstraint] Method not implemented. Constraints({:s}) are being ignored.'
        LOGGER.warning(msg.format(str(constraints)))
        return [True for _ in range(len(constraints))]

    @metered_subclass_method(METRICS_POOL)
    def SetConfig(self, resources: List[Tuple[str, Any]]) \
            -> List[Union[bool, Exception]]:
        """ Create/Update configuration for a list of service resources.
            Parameters:
                resources: List[Tuple[str, Any]]
                    List of tuples, each containing a resource_key pointing to
                    the resource to be modified, and a resource_value
                    containing the new value to be set.
            Returns:
                results: List[Union[bool, Exception]]
                    List of results for resource key changes requested.
                    Return values must be in the same order as the requested
                    resource keys. If a resource is properly set, True must be
                    returned; otherwise, the Exception that is raised during
                    the processing must be returned.
        """
        chk_type('resources', resources, list)
        if len(resources) == 0: return []

        msg = '[SetConfig] Method not implemented. Resources({:s}) are being ignored.'
        LOGGER.warning(msg.format(str(resources)))
        return [True for _ in range(len(resources))]

    @metered_subclass_method(METRICS_POOL)
    def DeleteConfig(self, resources: List[Tuple[str, Any]]) \
            -> List[Union[bool, Exception]]:
        """ Delete configuration for a list of service resources.
            Parameters:
                resources: List[Tuple[str, Any]]
                    List of tuples, each containing a resource_key pointing to
                    the resource to be modified, and a resource_value containing
                    possible additionally required values to locate the value
                    to be removed.
            Returns:
                results: List[Union[bool, Exception]]
                    List of results for resource key deletions requested.
                    Return values must be in the same order as the requested
                    resource keys. If a resource is properly deleted, True must
                    be returned; otherwise, the Exception that is raised during
                    the processing must be returned.
        """
        chk_type('resources', resources, list)
        if len(resources) == 0: return []

        msg = '[DeleteConfig] Method not implemented. Resources({:s}) are being ignored.'
        LOGGER.warning(msg.format(str(resources)))
        return [True for _ in range(len(resources))]

    def _init_settings(self):
        self.__switch_info = {}
        self.__port_map = {}
        self.__upf = {}
        self.__gnb = {}
        self.__ue_map = {}

        try:
            self.__settings = self.__settings_handler.get('/settings')
            LOGGER.info(f"{self.__service_label} with settings: {self.__settings}")
        except Exception as ex:
            LOGGER.error(f"Failed to retrieve service settings: {ex}")
            raise Exception(ex)

    def _parse_settings(self):
        try:
            switch_info = self.__settings.value[SWITCH_INFO]
        except Exception as ex:
            LOGGER.error(f"Failed to parse service settings: {ex}")
            raise Exception(ex)
        assert isinstance(switch_info, list), "Switch info object must be a list"

        for switch in switch_info:
            for switch_name, sw_info in switch.items():
                assert switch_name, "Invalid P4 switch name"
                assert isinstance(sw_info, dict), \
                    "Switch {} info must be a map with arch, dpid, port_list, fwd_list, routing_list, upf, gnb, and ue_list items)"
                assert sw_info[ARCH] in SUPPORTED_TARGET_ARCH_LIST, \
                    f"Switch {switch_name} - Supported P4 architectures are: {','.join(SUPPORTED_TARGET_ARCH_LIST)}"
                switch_dpid = sw_info[DPID]
                assert switch_dpid > 0, f"Switch {switch_name} - P4 switch dataplane ID {sw_info[DPID]} must be a positive integer"

                # Port list
                port_list = sw_info[PORT_LIST]
                assert isinstance(port_list, list),\
                    f"Switch {switch_name} port list must be a list with port_id, port_type, and vlan_id items"
                for port in port_list:
                    port_id = port[PORT_ID]
                    assert port_id >= 0, f"Switch {switch_name} - Invalid P4 switch port ID"
                    port_type = port[PORT_TYPE]
                    assert port_type in PORT_TYPES_STR_VALID, f"Switch {switch_name} - Valid P4 switch port types are: {','.join(PORT_TYPES_STR_VALID)}"
                    vlan_id = port[VLAN_ID]
                    assert chk_vlan_id(vlan_id), f"Switch {switch_name} - Invalid VLAN ID for port {port_id}"

                    if switch_name not in self.__port_map:
                        self.__port_map[switch_name] = {}
                    port_key = PORT_PREFIX + str(port_id)
                    if port_key not in self.__port_map[switch_name]:
                        self.__port_map[switch_name][port_key] = {}
                    self.__port_map[switch_name][port_key][PORT_ID] = port_id
                    self.__port_map[switch_name][port_key][PORT_TYPE] = port_type
                    self.__port_map[switch_name][port_key][VLAN_ID] = vlan_id
                    self.__port_map[switch_name][port_key][FORWARDING_LIST] = []
                    self.__port_map[switch_name][port_key][ROUTING_LIST] = []

                # Forwarding list
                fwd_list = sw_info[FORWARDING_LIST]
                assert isinstance(fwd_list, list), f"Switch {switch_name} forwarding list must be a list"
                for fwd_entry in fwd_list:
                    port_id = fwd_entry[PORT_ID]
                    assert port_id >= 0, f"Invalid port ID: {port_id}"
                    host_mac = fwd_entry[HOST_MAC]
                    assert chk_address_mac(host_mac), f"Invalid host MAC address {host_mac}"
                    host_label = ""
                    if HOST_LABEL in fwd_entry:
                        host_label = fwd_entry[HOST_LABEL]

                    # Retrieve entry from the port map
                    switch_port_entry = self._get_switch_port_in_port_map(switch_name, port_id)

                    host_facing_port = self._is_host_facing_port(switch_name, port_id)
                    LOGGER.info(f"Switch {switch_name} - Port {port_id}: Is host facing: {"True" if host_facing_port else "False"}")
                    switch_port_entry[FORWARDING_LIST].append(
                        {
                            HOST_MAC: host_mac,
                            HOST_LABEL: host_label
                        }
                    )

                # Routing list
                routing_list = sw_info[ROUTING_LIST]
                assert isinstance(routing_list, list), f"Switch {switch_name} routing list must be a list"
                for rt_entry in routing_list:
                    port_id = rt_entry[PORT_ID]
                    assert port_id >= 0, f"Invalid port ID: {port_id}"
                    ipv4_dst = rt_entry[IPV4_DST]
                    assert chk_address_ipv4(ipv4_dst), f"Invalid destination IPv4 address {ipv4_dst}"
                    ipv4_prefix_len = rt_entry[IPV4_PREFIX_LEN]
                    assert chk_prefix_len_ipv4(ipv4_prefix_len), f"Invalid IPv4 address prefix length {ipv4_prefix_len}"
                    mac_src = rt_entry[MAC_SRC]
                    assert chk_address_mac(mac_src), f"Invalid source MAC address {mac_src}"
                    mac_dst = rt_entry[MAC_DST]
                    assert chk_address_mac(mac_dst), f"Invalid destination MAC address {mac_dst}"

                    # Retrieve entry from the port map
                    switch_port_entry = self._get_switch_port_in_port_map(switch_name, port_id)

                    # Add routing entry
                    switch_port_entry[ROUTING_LIST].append(
                        {
                            PORT_ID: port_id,
                            IPV4_DST: ipv4_dst,
                            IPV4_PREFIX_LEN: ipv4_prefix_len,
                            MAC_SRC: mac_src,
                            MAC_DST: mac_dst
                        }
                    )
                
                # UPF
                upf = sw_info[UPF]

                self.__upf[UPLINK_PORT] = upf[UPLINK_PORT]
                assert self.__upf[UPLINK_PORT] >= 0, f"Invalid uplink UPF port: {self.__upf[UPLINK_PORT]}"

                self.__upf[UPLINK_IP] = upf[UPLINK_IP]
                assert chk_address_ipv4(self.__upf[UPLINK_IP]), f"Invalid uplink UPF IPv4 address {self.__upf[UPLINK_IP]}"

                self.__upf[UPLINK_MAC] = upf[UPLINK_MAC]
                assert chk_address_mac(self.__upf[UPLINK_MAC]), f"Invalid uplink UPF MAC address {self.__upf[UPLINK_MAC]}"

                self.__upf[DOWNLINK_PORT] = upf[DOWNLINK_PORT]
                assert self.__upf[DOWNLINK_PORT] >= 0, f"Invalid downlink UPF port: {self.__upf[DOWNLINK_PORT]}"

                self.__upf[DOWNLINK_IP] = upf[DOWNLINK_IP]
                assert chk_address_ipv4(self.__upf[DOWNLINK_IP]), f"Invalid downlink UPF IPv4 address {self.__upf[DOWNLINK_IP]}"

                self.__upf[DOWNLINK_MAC] = upf[DOWNLINK_MAC]
                assert chk_address_mac(self.__upf[DOWNLINK_MAC]), f"Invalid downlink UPF MAC address {self.__upf[DOWNLINK_MAC]}"

                slice_id = upf[SLICE_ID]
                assert slice_id >= 0, "Slice ID must be a non-negative integer"
                self.__upf[SLICE_ID] = slice_id

                teid = upf[TEID]
                assert teid >= 0, "TEID must be a non-negative integer"
                self.__upf[TEID] = teid

                app_id = upf[APP_ID]
                assert app_id >= 0, "App ID must be a non-negative integer"
                self.__upf[APP_ID] = app_id

                app_meter_id = upf[APP_METER_ID]
                assert app_meter_id >= 0, "App meter ID must be a non-negative integer"
                self.__upf[APP_METER_ID] = app_meter_id

                ctr_id = upf[CTR_ID]
                assert ctr_id >= 0, "Ctr ID must be a non-negative integer"
                self.__upf[CTR_ID] = ctr_id

                tc_id = upf[TC_ID]
                assert tc_id >= 0, "TC ID must be a non-negative integer"
                self.__upf[TC_ID] = tc_id

                tunnel_peer_id = upf[TUNNEL_PEER_ID]
                assert tunnel_peer_id >= 0, "Tunnel peer ID must be a non-negative integer"
                self.__upf[TUNNEL_PEER_ID] = tunnel_peer_id

                # gNB configuration
                gnb = sw_info[GNB]
                self.__gnb[IP] = gnb[IP]
                assert chk_address_ipv4(self.__gnb[IP]), f"Invalid 5G gNB IPv4 address {self.__gnb[IP]}"

                self.__gnb[MAC] = gnb[MAC]
                assert chk_address_mac(self.__gnb[MAC]), f"Invalid 5G gNB MAC address {self.__gnb[MAC]}"

                # UE list
                ue_list = sw_info[UE_LIST]
                assert isinstance(ue_list, list), f"Switch {switch_name} UE list must be a list"
                for ue in ue_list:
                    ue_id = ue[UE_ID]
                    assert ue_id, f"Empty UE ID: {UE_ID}"
                    ue_ip = ue[UE_IP]
                    assert chk_address_ipv4(ue_ip), "Invalid UE IPv4 address"
                    self.__ue_map[ue_ip] = {}
                    self.__ue_map[ue_ip][UE_ID] = ue_id
                    self.__ue_map[ue_ip][UE_IP] = ue_ip

                    # PDU list per UE
                    self.__ue_map[ue_ip][PDU_LIST] = []
                    pdu_session_list = ue[PDU_LIST]
                    assert isinstance(pdu_session_list, list), f"UE {ue_id} PDU session list must be a list"
                    for pdu in pdu_session_list:
                        pdu_id = pdu[PDU_SESSION_ID]
                        assert pdu_id >= 0, "PDU ID must be a non-negative integer"
                        assert pdu_id == DEF_SESSION_METER_ID, "Better use PDU session ID = 0, as only this is supported for now"
                        dnn = pdu[DNN]
                        assert dnn, "Data network name is invalid"
                        session_type_str = pdu[PDU_SESSION_TYPE]
                        assert session_type_str == ETHER_TYPE_IPV4, f"Only supported PDU session type for now is {ETHER_TYPE_IPV4}"
                        gtpu_tunnel = pdu[GTPU_TUNNEL]
                        assert isinstance(gtpu_tunnel, dict), "GTP-U tunnel info must be a map with uplink and downlink items)"

                        gtpu_ul = gtpu_tunnel[UPLINK]
                        assert isinstance(gtpu_ul, dict), "GTP-U tunnel UL info must be a map with src and dst IP items)"
                        assert chk_address_ipv4(gtpu_ul[SRC]), f"Invalid GTP-U UL src IPv4 address {gtpu_ul[SRC]}"
                        assert chk_address_ipv4(gtpu_ul[DST]), f"Invalid GTP-U UL dst IPv4 address {gtpu_ul[DST]}"

                        gtpu_dl = gtpu_tunnel[DOWNLINK]
                        assert isinstance(gtpu_dl, dict), "GTP-U tunnel DL info must be a map with src and dst IP items)"
                        assert chk_address_ipv4(gtpu_dl[SRC]), f"Invalid GTP-U DL src IPv4 address {gtpu_dl[SRC]}"
                        assert chk_address_ipv4(gtpu_dl[DST]), f"Invalid GTP-U DL dst IPv4 address {gtpu_dl[DST]}"

                        self.__ue_map[ue_ip][PDU_LIST].append(pdu)
                    
                    # QoS flows per UE
                    self.__ue_map[ue_ip][QOS_FLOWS] = []
                    qos_flows_list = ue[QOS_FLOWS]
                    assert isinstance(qos_flows_list, list), f"UE {ue_id} QoS flows' list must be a list"
                    for flow in qos_flows_list:
                        qfi = flow[QFI]
                        assert qfi >= 0, "QFI must be a non-negative integer"
                        fiveqi = flow[FIVEQI]
                        assert fiveqi >= 0, "5QI must be a non-negative integer"
                        qos_type = flow[QOS_TYPE]
                        assert qos_type.casefold() in (s.casefold() for s in QOS_TYPES_STR_VALID), \
                            f"UE {ue_id} - Valid QoS types are: {','.join(QOS_TYPES_STR_VALID)}"
                        self.__ue_map[ue_ip][QOS_FLOWS].append(flow)

                self.__switch_info[switch_name] = sw_info

    def _print_settings(self):
        LOGGER.info(f"--------------- {self.__service.name} settings ---------------")
        LOGGER.info("--- Topology info")
        for switch_name, switch_info in self.__switch_info.items():
            LOGGER.info(f"\t Device {switch_name}")
            LOGGER.info(f"\t\t| Target P4 architecture: {switch_info[ARCH]}")
            LOGGER.info(f"\t\t|          Data plane ID: {switch_info[DPID]}")
            LOGGER.info("\t\t|   5G UPF Configuration:")
            LOGGER.info(f"\t\t\t|        Uplink Port: {self.__upf[UPLINK_PORT]}")
            LOGGER.info(f"\t\t\t|        Uplink   IP: {self.__upf[UPLINK_IP]}")
            LOGGER.info(f"\t\t\t|        Uplink  MAC: {self.__upf[UPLINK_MAC]}")
            LOGGER.info(f"\t\t\t|      Downlink Port: {self.__upf[DOWNLINK_PORT]}")
            LOGGER.info(f"\t\t\t|      Downlink   IP: {self.__upf[DOWNLINK_IP]}")
            LOGGER.info(f"\t\t\t|      Downlink  MAC: {self.__upf[DOWNLINK_MAC]}")
            LOGGER.info(f"\t\t\t|     Slice       ID: {self.__upf[SLICE_ID]}")
            LOGGER.info(f"\t\t\t| Tunnel Endpoint ID: {self.__upf[TEID]}")
            LOGGER.info(f"\t\t\t|     App         ID: {self.__upf[APP_ID]}")
            LOGGER.info(f"\t\t\t|     App Meter   ID: {self.__upf[APP_METER_ID]}")
            LOGGER.info(f"\t\t\t|     Ctr         ID: {self.__upf[CTR_ID]}")
            LOGGER.info(f"\t\t\t|     TC          ID: {self.__upf[TC_ID]}")
            LOGGER.info(f"\t\t\t|     Tunnel Peer ID: {self.__upf[TUNNEL_PEER_ID]}\n")
            # LOGGER.info("\n")
            LOGGER.info("\t\t|   5G gNB Configuration:")
            LOGGER.info(f"\t\t\t|       5G gNB  IP: {self.__gnb[IP]}")
            LOGGER.info(f"\t\t\t|       5G gNB MAC: {self.__gnb[MAC]}\n")
            LOGGER.info("\t\t|               Port Map:")
            for _, port_map in self.__port_map[switch_name].items():
                LOGGER.info(f"\t\t\t|        Port ID: {port_map[PORT_ID]}")
                LOGGER.info(f"\t\t\t|      Port type: {port_map[PORT_TYPE]}")
                LOGGER.info(f"\t\t\t|   Port VLAN ID: {port_map[VLAN_ID]}")
                LOGGER.info(f"\t\t\t|       FWD list: {port_map[FORWARDING_LIST]}")
                LOGGER.info(f"\t\t\t|   Routing list: {port_map[ROUTING_LIST]}\n")
            LOGGER.info("\t\t|                UE List:")
            for ue_key, ue_info in self.__ue_map.items():
                assert ue_key == ue_info[UE_IP], "UE key is not the UE IPv4 address"
                ue_ip = ue_info[UE_IP]
                LOGGER.info(f"\t\t\t|          UE ID: {ue_info[UE_ID]}")
                LOGGER.info(f"\t\t\t|          UE IP: {ue_info[UE_IP]}")
                for pdu in self.__ue_map[ue_ip][PDU_LIST]:
                    LOGGER.info(f"\t\t\t\t|          PDU session ID: {pdu[PDU_SESSION_ID]}")
                    LOGGER.info(f"\t\t\t\t|                     DNN: {pdu[DNN]}")
                    LOGGER.info(f"\t\t\t\t|        PDU session type: {pdu[PDU_SESSION_TYPE]}")
                    LOGGER.info(f"\t\t\t\t| GTP-U tunnel UL Src. IP: {pdu[GTPU_TUNNEL][UPLINK][SRC]}")
                    LOGGER.info(f"\t\t\t\t| GTP-U tunnel UL Dst. IP: {pdu[GTPU_TUNNEL][UPLINK][DST]}")
                    LOGGER.info(f"\t\t\t\t| GTP-U tunnel DL Src. IP: {pdu[GTPU_TUNNEL][DOWNLINK][SRC]}")
                    LOGGER.info(f"\t\t\t\t| GTP-U tunnel DL Dst. IP: {pdu[GTPU_TUNNEL][DOWNLINK][DST]}\n")
                for flow in self.__ue_map[ue_ip][QOS_FLOWS]:
                    LOGGER.info(f"\t\t\t\t|                QoS  QFI: {flow[QFI]}")
                    LOGGER.info(f"\t\t\t\t|                QoS  5QI: {flow[FIVEQI]}")
                    LOGGER.info(f"\t\t\t\t|                QoS Type: {flow[QOS_TYPE]}\n")
        LOGGER.info("-------------------------------------------------------")

    def _get_switch_port_in_port_map(self, switch_name : str, port_id : int) -> Dict:
        assert switch_name, "A valid switch name must be used as a key to the port map"
        assert port_id > 0, "A valid switch port ID must be used as a key to a switch's port map"
        switch_entry = self.__port_map[switch_name]
        assert switch_entry, f"Switch {switch_name} does not exist in the port map"
        port_key = PORT_PREFIX + str(port_id)
        assert switch_entry[port_key], f"Port with ID {port_id} does not exist in the switch map"

        return switch_entry[port_key]
    
    def _get_port_type_of_switch_port(self, switch_name : str, port_id : int) -> str:
        switch_port_entry = self._get_switch_port_in_port_map(switch_name, port_id)
        return switch_port_entry[PORT_TYPE]
    
    def _get_vlan_id_of_switch_port(self, switch_name : str, port_id : int) -> int:
        switch_port_entry = self._get_switch_port_in_port_map(switch_name, port_id)
        return switch_port_entry[VLAN_ID]

    def _get_fwd_list_of_switch_port(self, switch_name : str, port_id : int) -> List [Tuple]:
        switch_port_entry = self._get_switch_port_in_port_map(switch_name, port_id)
        return switch_port_entry[FORWARDING_LIST]
    
    def _get_routing_list_of_switch_port(self, switch_name : str, port_id : int) -> List [Tuple]:
        switch_port_entry = self._get_switch_port_in_port_map(switch_name, port_id)
        return switch_port_entry[ROUTING_LIST]

    def _is_host_facing_port(self, switch_name : str, port_id : int) -> bool:
        return self._get_port_type_of_switch_port(switch_name, port_id) == PORT_TYPE_HOST

    def _create_rules_uplink(
            self,
            device_obj : Device, # type: ignore
            port_id : int,
            next_id : int,
            action : ConfigActionEnum): # type: ignore
        dev_name = device_obj.name
        vlan_id = self._get_vlan_id_of_switch_port(switch_name=dev_name, port_id=port_id)

        rules  = []

        # Port setup rules
        try:
            rules += rules_set_up_port(
                port_id=port_id,
                port_type=PORT_TYPE_HOST,
                fwd_type=FORWARDING_TYPE_BRIDGING,
                vlan_id=vlan_id,
                action=action
            )
        except Exception as ex:
            LOGGER.error("Error while creating port setup rules")
            raise Exception(ex)

        ### UPF rules
        try:
            rules += rules_set_up_upf_interface(
                port_id=port_id,
                ipv4_dst=self.__upf[UPLINK_IP],  # UPF's N3 interface
                ipv4_prefix_len=32,
                gtpu_value=GTPU_VALID,
                slice_id=self.__upf[SLICE_ID],
                action=action
            )
        except Exception as ex:
            LOGGER.error("Error while creating UPF interface rule")
            raise Exception(ex)
        
        try:
            rules += rules_set_up_upf_uplink_sessions(
                port_id=port_id,
                tun_ip_address=self.__upf[UPLINK_IP],  # UPF's N3 interface
                teid=self.__upf[TEID],
                session_meter_id=DEF_SESSION_METER_ID,
                action=action
            )
        except Exception as ex:
            LOGGER.error("Error while creating UPF UL session rule")
            raise Exception(ex)
        
        # UE-specific rules
        for _, ue_info in self.__ue_map.items():
            try:
                rules += rules_set_up_upf_uplink_terminations(
                    port_id=port_id,
                    ue_session_id=ue_info[UE_IP],  # UE's IPv4 address
                    app_id=self.__upf[APP_ID],
                    ctr_id=self.__upf[CTR_ID],
                    app_meter_id=self.__upf[APP_METER_ID],
                    tc_id=self.__upf[TC_ID],
                    action=action
                )
            except Exception as ex:
                LOGGER.error("Error while creating UPF termination rule")
                raise Exception(ex)

        # L2 Forwarding rules
        fwd_list = self._get_fwd_list_of_switch_port(switch_name=dev_name, port_id=next_id)
        for host_map in fwd_list:
            mac_dst = host_map[HOST_MAC]
            label = host_map[HOST_LABEL]
            LOGGER.info(f"\t | Switch {dev_name} - Port {port_id} - Creating rule for host MAC: {mac_dst} - label: {label}")
            try:
                ### Bridging rules
                rules += rules_set_up_fwd_bridging(
                    port_id=port_id,
                    vlan_id=vlan_id,
                    eth_dst=mac_dst,
                    next_id=next_id,
                    action=action
                )
            except Exception as ex:
                LOGGER.error("Error while creating bridging rule")
                raise Exception(ex)

        try:
            ### Pre-next VLAN rule
            rules += rules_set_up_pre_next_vlan(
                port_id=port_id,
                next_id=next_id,
                vlan_id=vlan_id,
                action=action
            )
        except Exception as ex:
            LOGGER.error("Error while creating pre-next VLAN rule")
            raise Exception(ex)

        ### Static routing rules
        routing_list = self._get_routing_list_of_switch_port(switch_name=dev_name, port_id=port_id)
        for rt_entry in routing_list:
            LOGGER.info(f"\t | Switch {dev_name} - Port {port_id} - Route to dst {rt_entry[IPV4_DST]}/{rt_entry[IPV4_PREFIX_LEN]}, with MAC src {rt_entry[MAC_SRC]} and dst {rt_entry[MAC_DST]}")

            try:
                ### Next profile for hashed routing
                rules += rules_set_up_next_profile_hashed_routing(
                    port_id=port_id,
                    next_id=next_id,
                    eth_src=rt_entry[MAC_SRC],  # UPF's N6 interface (self.__upf[DOWNLINK_MAC])
                    eth_dst=rt_entry[MAC_DST],  # Data network's N6 interface
                    action=action
                )
            except Exception as ex:
                LOGGER.error("Error while creating next profile for hashed routing")
                raise Exception(ex)

            try:
                ### Next hashed for routing
                rules += rules_set_up_next_hashed(
                    port_id=port_id,
                    next_id=next_id,
                    action=action
                )
                ### Route towards destination
                rules += rules_set_up_routing(
                    port_id=port_id,
                    ipv4_dst=rt_entry[IPV4_DST],
                    ipv4_prefix_len=rt_entry[IPV4_PREFIX_LEN],
                    next_id=next_id,
                    action=action
                )
            except Exception as ex:
                LOGGER.error("Error while creating static L3 routing rules")
                raise Exception(ex)

        return rules
    
    def _create_rules_downlink(
            self,
            device_obj : Device, # type: ignore
            port_id : int,
            next_id : int,
            action : ConfigActionEnum): # type: ignore
        dev_name = device_obj.name
        vlan_id = self._get_vlan_id_of_switch_port(switch_name=dev_name, port_id=port_id)

        rules  = []

        # Port setup
        try:
            rules += rules_set_up_port(
                port_id=port_id,
                port_type=PORT_TYPE_HOST,
                fwd_type=FORWARDING_TYPE_BRIDGING,
                vlan_id=vlan_id,
                action=action
            )
        except Exception as ex:
            LOGGER.error("Error while creating port setup rules")
            raise Exception(ex)

        ### UPF
        for _, ue_info in self.__ue_map.items():
            try:
                rules += rules_set_up_upf_interface(
                    port_id=port_id,
                    ipv4_dst=ue_info[UE_IP],
                    ipv4_prefix_len=32,
                    gtpu_value=GTPU_INVALID,
                    slice_id=self.__upf[SLICE_ID],
                    action=action
                )
            except Exception as ex:
                LOGGER.error("Error while creating UPF interface rule")
                raise Exception(ex)
            
            try:
                rules += rules_set_up_upf_downlink_sessions(
                    port_id=port_id,
                    ipv4_dst=ue_info[UE_IP],
                    session_meter_id=ue_info[PDU_LIST][0][PDU_SESSION_ID],  # Should match DEF_SESSION_METER_ID
                    tun_peer_id=self.__upf[TUNNEL_PEER_ID],
                    action=action
                )
            except Exception as ex:
                LOGGER.error("Error while creating UPF DL session rule")
                raise Exception(ex)
            
            try:
                rules += rules_set_up_upf_downlink_terminations(
                    port_id=port_id,
                    ue_session_id=ue_info[UE_IP],  # UE's IPv4 address
                    app_id=self.__upf[APP_ID],
                    ctr_id=self.__upf[CTR_ID],
                    app_meter_id=self.__upf[APP_METER_ID],
                    tc_id=self.__upf[TC_ID],
                    teid=self.__upf[TEID],
                    qfi=ue_info[QOS_FLOWS][0][QFI],
                    action=action
                )
            except Exception as ex:
                LOGGER.error("Error while creating UPF DL termination rule")
                raise Exception(ex)
        
        try:
            rules += rules_set_up_upf_downlink_ig_tunnel_peers(
                port_id=port_id,
                tun_peer_id=self.__upf[TUNNEL_PEER_ID],
                tun_dst_addr=self.__upf[UPLINK_IP],  # UPF's N3 interface
                action=action
            )
        except Exception as ex:
            LOGGER.error("Error while creating UPF DL ingress tunnel peers rule")
            raise Exception(ex)
        
        try:
            rules += rules_set_up_upf_downlink_eg_tunnel_peers(
                port_id=port_id,
                tun_peer_id=self.__upf[TUNNEL_PEER_ID],
                tun_src_addr=self.__upf[UPLINK_IP],  # UPF's N3 interface
                tun_dst_addr=self.__gnb[IP],         # gNB's N3 interface
                tun_src_port=GTP_PORT,               # GTP-U port
                action=action
            )
        except Exception as ex:
            LOGGER.error("Error while creating UPF DL egress tunnel peers rule")
            raise Exception(ex)

        # L2 Forwarding
        fwd_list = self._get_fwd_list_of_switch_port(switch_name=dev_name, port_id=next_id)
        for host_map in fwd_list:
            mac_dst = host_map[HOST_MAC]
            label = host_map[HOST_LABEL]
            LOGGER.info(f"\t | Switch {dev_name} - Port {port_id} - Creating rule for host MAC: {mac_dst} - label: {label}")
            try:
                ### Bridging
                rules += rules_set_up_fwd_bridging(
                    port_id=port_id,
                    vlan_id=vlan_id,
                    eth_dst=mac_dst,
                    next_id=next_id,
                    action=action
                )
            except Exception as ex:
                LOGGER.error("Error while creating bridging rule")
                raise Exception(ex)

        try:
            ### Pre-next VLAN
            rules += rules_set_up_pre_next_vlan(
                port_id=port_id,
                next_id=next_id,
                vlan_id=vlan_id,
                action=action
            )
        except Exception as ex:
            LOGGER.error("Error while creating pre-next VLAN rule")
            raise Exception(ex)

        ### Static routing
        routing_list = self._get_routing_list_of_switch_port(switch_name=dev_name, port_id=port_id)
        for rt_entry in routing_list:
            LOGGER.info(f"\t | Switch {dev_name} - Port {port_id} - Route to dst {rt_entry[IPV4_DST]}/{rt_entry[IPV4_PREFIX_LEN]}, with MAC src {rt_entry[MAC_SRC]} and dst {rt_entry[MAC_DST]}")

            try:
                ### Next profile for hashed routing
                rules += rules_set_up_next_profile_hashed_routing(
                    port_id=port_id,
                    next_id=next_id,
                    eth_src=rt_entry[MAC_SRC],  # UPF's N3 interface (self.__upf[UPLINK_MAC])
                    eth_dst=rt_entry[MAC_DST],  # gNB's N3 interface (self.__gnb[MAC])
                    action=action
                )
            except Exception as ex:
                LOGGER.error("Error while creating next profile for hashed routing")
                raise Exception(ex)

            try:
                ### Next hashed for routing
                rules += rules_set_up_next_hashed(
                    port_id=port_id,
                    next_id=next_id,
                    action=action
                )
                ### Route towards destination
                rules += rules_set_up_routing(
                    port_id=port_id,
                    ipv4_dst=rt_entry[IPV4_DST],
                    ipv4_prefix_len=rt_entry[IPV4_PREFIX_LEN],
                    next_id=next_id,
                    action=action
                )
            except Exception as ex:
                LOGGER.error("Error while creating static L3 routing rules")
                raise Exception(ex)

        return rules

