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

import json, logging, re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union
from common.method_wrappers.Decorator import MetricsPool, metered_subclass_method
from common.proto.context_pb2 import ConfigRule, Device, DeviceId, EndPoint, EndPointId, Service
from common.tools.grpc.Tools import grpc_message_to_json_string
from common.tools.object_factory.ConfigRule import json_config_rule_delete, json_config_rule_set
from common.tools.object_factory.Device import json_device_id
from common.type_checkers.Checkers import chk_type
from service.service.service_handler_api._ServiceHandler import _ServiceHandler
from service.service.service_handler_api.SettingsHandler import SettingsHandler
from service.service.service_handler_api.Tools import get_device_endpoint_uuids, get_endpoint_matching
from service.service.task_scheduler.TaskExecutor import TaskExecutor


LOGGER = logging.getLogger(__name__)

METRICS_POOL = MetricsPool('Service', 'Handler', labels={'handler': 'l3nm_ryu'})

RE_DEV_EP_SETTINGS = re.compile(r'/device\[(.*?)\]/endpoint\[(.*?)\]/settings')


def get_ip_from_endpoint_settings(
    device_obj : Device, endpoint_obj : EndPoint, settings_handler : SettingsHandler
) -> Optional[str]:
    device_uuid    = device_obj.device_id.device_uuid.uuid
    ep_device_uuid = endpoint_obj.endpoint_id.device_id.device_uuid.uuid
    if device_uuid != ep_device_uuid:
        MSG = 'Malformed endpoint: device_uuid({:s}) != endpoint.device_uuid({:s})'
        raise Exception(MSG.format(str(device_uuid), str(ep_device_uuid)))

    endpoint_settings = settings_handler.get_endpoint_settings(device_obj, endpoint_obj)
    if endpoint_settings is None: return None

    json_settings : Dict = endpoint_settings.value
    if 'address_ip' in json_settings: return json_settings['address_ip']
    if 'ip_address' in json_settings: return json_settings['ip_address']

    MSG = 'IP Address not found. Tried: address_ip and ip_address. endpoint_obj={:s} settings={:s}'
    LOGGER.warning(MSG.format(str(endpoint_obj), str(json_settings)))
    return None


@dataclass
class ServiceData:
    src_device_uuid   : str
    src_device_name   : str
    src_endpoint_uuid : str
    src_endpoint_name : str
    src_ipv4_address  : str

    dst_device_uuid   : str
    dst_device_name   : str
    dst_endpoint_uuid : str
    dst_endpoint_name : str
    dst_ipv4_address  : str

    @classmethod
    def create(
        cls, src_device_obj : Device, src_endpoint_obj : EndPoint,
        dst_device_obj : Device, dst_endpoint_obj : EndPoint,
        settings_handler : SettingsHandler
    ) -> 'ServiceData':
        src_device_uuid    = src_device_obj.device_id.device_uuid.uuid
        src_ep_device_uuid = src_endpoint_obj.endpoint_id.device_id.device_uuid.uuid
        if src_device_uuid != src_ep_device_uuid:
            MSG = 'Malformed endpoint: src_device_uuid({:s}) != src_endpoint.device_uuid({:s})'
            raise Exception(MSG.format(str(src_device_uuid), str(src_ep_device_uuid)))

        dst_device_uuid    = dst_device_obj.device_id.device_uuid.uuid
        dst_ep_device_uuid = dst_endpoint_obj.endpoint_id.device_id.device_uuid.uuid
        if dst_device_uuid != dst_ep_device_uuid:
            MSG = 'Malformed endpoint: dst_device_uuid({:s}) != dst_endpoint.device_uuid({:s})'
            raise Exception(MSG.format(str(dst_device_uuid), str(dst_ep_device_uuid)))

        src_ipv4_address = get_ip_from_endpoint_settings(src_device_obj, src_endpoint_obj, settings_handler)
        dst_ipv4_address = get_ip_from_endpoint_settings(dst_device_obj, dst_endpoint_obj, settings_handler)

        return cls(
            src_device_uuid   = src_device_obj.device_id.device_uuid.uuid,
            src_device_name   = src_device_obj.name,
            src_endpoint_uuid = src_endpoint_obj.endpoint_id.endpoint_uuid.uuid,
            src_endpoint_name = src_endpoint_obj.name,
            src_ipv4_address  = src_ipv4_address,
            dst_device_uuid   = dst_device_obj.device_id.device_uuid.uuid,
            dst_device_name   = dst_device_obj.name,
            dst_endpoint_uuid = dst_endpoint_obj.endpoint_id.endpoint_uuid.uuid,
            dst_endpoint_name = dst_endpoint_obj.name,
            dst_ipv4_address  = dst_ipv4_address,
        )

    def get_flow_rule_name(self, reverse : bool = False) -> str:
        device_names = [self.src_device_name, self.dst_device_name]
        if reverse: device_names = list(reversed(device_names))
        return '-'.join(device_names)

    def get_ip_addresses(self, reverse : bool = False) -> Tuple[str, str]:
        ipv4_addresses = [self.src_ipv4_address, self.dst_ipv4_address]
        if reverse: ipv4_addresses = list(reversed(ipv4_addresses))
        return ipv4_addresses


def compose_flow_rule(
    device_name : str, dpid : str, in_port : str, out_port : str,
    service_data : ServiceData, reverse : bool, is_delete : bool
) -> ConfigRule:
    ports = [in_port, out_port]
    if reverse: ports = list(reversed(ports))
    in_port, out_port = ports

    flow_rule_name = service_data.get_flow_rule_name(reverse=reverse)
    ipv4_addresses = service_data.get_ip_addresses(reverse=reverse)

    RSRC_KEY_TMPL = '/device[{:s}]/flow[{:s}]'
    resource_key = RSRC_KEY_TMPL.format(device_name, flow_rule_name)
    resource_value = {
        'dpid'        : dpid,
        'in-port'     : in_port,
        'out-port'    : out_port,
        'src-ip-addr' : ipv4_addresses[ 0],
        'dst-ip-addr' : ipv4_addresses[-1],
    }
    json_config_rule_method = json_config_rule_delete if is_delete else json_config_rule_set
    flow_rule = json_config_rule_method(resource_key, resource_value)
    return ConfigRule(**flow_rule)


class L3NMRyuServiceHandler(_ServiceHandler):
    def __init__(   # pylint: disable=super-init-not-called
        self, service : Service, task_executor : TaskExecutor, **settings
    ) -> None:
        self.__service = service
        self.__task_executor = task_executor
        self.__settings_handler = SettingsHandler(service.service_config, **settings)

    def _get_device_endpoint_obj_from_id(
        self, endpoint_id : EndPointId
    ) -> Tuple[Device, EndPoint]:
        device_uuid   = endpoint_id.device_id.device_uuid.uuid
        endpoint_uuid = endpoint_id.endpoint_uuid.uuid
        device_obj    = self.__task_executor.get_device(DeviceId(**json_device_id(device_uuid)))
        endpoint_obj  = get_endpoint_matching(device_obj, endpoint_uuid)
        return device_obj, endpoint_obj

    def _get_device_endpoint_obj_from_key(
        self, endpoint_key : Tuple[str, str, Optional[str]]
    ) -> Tuple[Device, EndPoint]:
        device_uuid, endpoint_uuid = get_device_endpoint_uuids(endpoint_key)
        device_obj   = self.__task_executor.get_device(DeviceId(**json_device_id(device_uuid)))
        endpoint_obj = get_endpoint_matching(device_obj, endpoint_uuid)
        return device_obj, endpoint_obj

    def _configure_hop_flow_rules(
        self, src_ep_key : Tuple[str, str, Optional[str]], dst_ep_key : Tuple[str, str, Optional[str]],
        service_data : ServiceData, is_delete : bool = False
    ) -> None:
        src_dev, src_ep = self._get_device_endpoint_obj_from_key(src_ep_key)
        dst_dev, dst_ep = self._get_device_endpoint_obj_from_key(dst_ep_key)
        if src_dev.device_id.device_uuid.uuid != dst_dev.device_id.device_uuid.uuid:
            MSG = 'Mismatching device for endpoints: {:s}-{:s}'
            raise Exception(MSG.format(str(src_ep_key), str(dst_ep_key)))

        src_ctrl = self.__task_executor.get_device_controller(src_dev)
        dst_ctrl = self.__task_executor.get_device_controller(dst_dev)
        if src_ctrl != dst_ctrl:
            MSG = 'Mismatching controller for endpoints: {:s}-{:s}'
            raise Exception(MSG.format(str(src_ep_key), str(dst_ep_key)))

        device_name = src_ep.name.split('-')[0]
        device_dpid = src_dev.name

        ctrl = src_ctrl
        LOGGER.debug('Ctrl: {:s}'.format(str(ctrl.name)))

        del ctrl.device_config.config_rules[:]
        del ctrl.device_endpoints[:]

        forward_flow_rule = compose_flow_rule(
            device_name, device_dpid, src_ep.name, dst_ep.name, service_data,
            reverse=False, is_delete=is_delete
        )
        MSG = 'Forward Config Rule: {:s}'
        LOGGER.debug(MSG.format(grpc_message_to_json_string(forward_flow_rule)))
        ctrl.device_config.config_rules.append(forward_flow_rule)

        reverse_flow_rule = compose_flow_rule(
            device_name, device_dpid, src_ep.name, dst_ep.name, service_data,
            reverse=True, is_delete=is_delete
        )
        MSG = 'Reverse Config Rule: {:s}'
        LOGGER.debug(MSG.format(grpc_message_to_json_string(reverse_flow_rule)))
        ctrl.device_config.config_rules.append(reverse_flow_rule)

        self.__task_executor.configure_device(ctrl)

    @metered_subclass_method(METRICS_POOL)
    def SetEndpoint(
        self, endpoints : List[Tuple[str, str, Optional[str]]], connection_uuid : Optional[str] = None
    ) -> List[Union[bool, Exception]]:
        LOGGER.debug('[SetEndpoint] endpoints = {:s}'.format(str(endpoints)))
        chk_type('endpoints', endpoints, list)

        if len(endpoints) < 2:
            LOGGER.warning('nothing done: not enough endpoints')
            return []

        service_endpoint_ids = list(self.__service.service_endpoint_ids)
        src_device_obj, src_endpoint_obj = self._get_device_endpoint_obj_from_id(service_endpoint_ids[ 0])
        dst_device_obj, dst_endpoint_obj = self._get_device_endpoint_obj_from_id(service_endpoint_ids[-1])
        service_data = ServiceData.create(
            src_device_obj, src_endpoint_obj, dst_device_obj, dst_endpoint_obj, self.__settings_handler
        )

        results = []
        try:
            it_endpoints = iter(endpoints)
            for src_ep_key, dst_ep_key in zip(it_endpoints, it_endpoints):
                self._configure_hop_flow_rules(src_ep_key, dst_ep_key, service_data, is_delete=False)
                results.append(True)
            return results
        except Exception as e:
            LOGGER.exception("Error in SetEndpoint")
            return [e]

    @metered_subclass_method(METRICS_POOL)
    def DeleteEndpoint(
        self, endpoints : List[Tuple[str, str, Optional[str]]], connection_uuid : Optional[str] = None
    ) -> List[Union[bool, Exception]]:
        LOGGER.debug('[DeleteEndpoint] endpoints = {:s}'.format(str(endpoints)))
        chk_type('endpoints', endpoints, list)

        if len(endpoints) < 2:
            LOGGER.warning('nothing done: not enough endpoints')
            return []

        service_endpoint_ids = list(self.__service.service_endpoint_ids)
        src_device_obj, src_endpoint_obj = self._get_device_endpoint_obj_from_id(service_endpoint_ids[ 0])
        dst_device_obj, dst_endpoint_obj = self._get_device_endpoint_obj_from_id(service_endpoint_ids[-1])
        service_data = ServiceData.create(
            src_device_obj, src_endpoint_obj, dst_device_obj, dst_endpoint_obj, self.__settings_handler
        )

        results = []
        try:
            it_endpoints = iter(endpoints)
            for src_ep_key, dst_ep_key in zip(it_endpoints, it_endpoints):
                self._configure_hop_flow_rules(src_ep_key, dst_ep_key, service_data, is_delete=True)
                results.append(True)
            return results
        except Exception as e:
            LOGGER.exception("Error in SetEndpoint")
            return [e]

    @metered_subclass_method(METRICS_POOL)
    def SetConstraint(self, constraints : List[Tuple[str, Any]]) -> List[Union[bool, Exception]]:
        chk_type('constraints', constraints, list)
        if len(constraints) == 0: return []

        msg = '[SetConstraint] Method not implemented. Constraints({:s}) are being ignored.'
        LOGGER.warning(msg.format(str(constraints)))
        return [True for _ in range(len(constraints))]

    @metered_subclass_method(METRICS_POOL)
    def DeleteConstraint(self, constraints : List[Tuple[str, Any]]) -> List[Union[bool, Exception]]:
        chk_type('constraints', constraints, list)
        if len(constraints) == 0: return []

        msg = '[DeleteConstraint] Method not implemented. Constraints({:s}) are being ignored.'
        LOGGER.warning(msg.format(str(constraints)))
        return [True for _ in range(len(constraints))]

    @metered_subclass_method(METRICS_POOL)
    def SetConfig(self, resources : List[Tuple[str, Any]]) -> List[Union[bool, Exception]]:
        chk_type('resources', resources, list)
        if len(resources) == 0: return []

        results = []
        for resource in resources:
            try:
                resource_value = json.loads(resource[1])
                self.__settings_handler.set(resource[0], resource_value)
                results.append(True)
            except Exception as e: # pylint: disable=broad-except
                LOGGER.exception('Unable to SetConfig({:s})'.format(str(resource)))
                results.append(e)

        return results

    @metered_subclass_method(METRICS_POOL)
    def DeleteConfig(self, resources : List[Tuple[str, Any]]) -> List[Union[bool, Exception]]:
        chk_type('resources', resources, list)
        if len(resources) == 0: return []

        results = []
        for resource in resources:
            try:
                self.__settings_handler.delete(resource[0])
            except Exception as e: # pylint: disable=broad-except
                LOGGER.exception('Unable to DeleteConfig({:s})'.format(str(resource)))
                results.append(e)

        return results
