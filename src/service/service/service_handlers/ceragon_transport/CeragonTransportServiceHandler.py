# Copyright 2026 Ceragon Networks Ltd. & ETSI TeraFlowSDN Authors
#
# Licensed under the BSD 3-Clause License (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://opensource.org/licenses/BSD-3-Clause
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Service handler for Ceragon radio hops
======================================
Registered for L2NM and L3NM services on devices driven by the Ceragon driver,
so services created through the IETF Network Slice (RFC 9543), L2VPN
(RFC 8466) or L3VPN (RFC 8299) interfaces reach the radios on their path.

TeraFlowSDN hands this handler the endpoints of each radio on a connection
(an Ethernet port and a radio sector per device). For each device it writes a
transport slice (a VLAN bridge between those endpoints) when the service is
tagged on the radio, plus the radio and ACM settings carried in the service
settings. See ConfigRules.py for the rules.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple, Union

from common.method_wrappers.Decorator import MetricsPool, metered_subclass_method
from common.proto.context_pb2 import ConfigRule, DeviceId, Service, ServiceTypeEnum
from common.tools.object_factory.Device import json_device_id
from common.type_checkers.Checkers import chk_type
from service.service.service_handler_api._ServiceHandler import _ServiceHandler
from service.service.service_handler_api.SettingsHandler import SettingsHandler
from service.service.service_handler_api.Tools import get_device_endpoint_uuids, get_endpoint_matching
from service.service.task_scheduler.TaskExecutor import TaskExecutor
from .ConfigRules import compose_setup_rules, compose_teardown_rules, resolve_bandwidth_mbps, resolve_vlan

LOGGER = logging.getLogger(__name__)

METRICS_POOL = MetricsPool('Service', 'Handler', labels={'handler': 'ceragon_transport'})

_ENDPOINT_SETTINGS_RE = re.compile(r'^/device\[[^\]]+\]/endpoint\[[^\]]+\]/settings$')


class CeragonTransportServiceHandler(_ServiceHandler):
    def __init__(   # pylint: disable=super-init-not-called
        self, service : Service, task_executor : TaskExecutor, **settings
    ) -> None:
        self.__service = service
        self.__task_executor = task_executor
        self.__settings_handler = SettingsHandler(service.service_config, **settings)

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _service_settings(self) -> Dict[str, Any]:
        node = self.__settings_handler.get('/settings')
        return dict(node.value) if node is not None and isinstance(node.value, dict) else {}

    def _access_point_settings(self) -> List[Dict[str, Any]]:
        """Endpoint settings anywhere on the service: the VLAN used at its access points."""
        found: List[Dict[str, Any]] = []
        for config_rule in self.__service.service_config.config_rules:
            if config_rule.WhichOneof('config_rule') != 'custom': continue
            if not _ENDPOINT_SETTINGS_RE.match(config_rule.custom.resource_key): continue
            try:
                value = json.loads(config_rule.custom.resource_value)
            except ValueError:
                continue
            if isinstance(value, dict): found.append(value)
        return found

    def _capacity_gbps(self) -> Optional[float]:
        for constraint in self.__service.service_constraints:
            if constraint.WhichOneof('constraint') == 'sla_capacity':
                return float(constraint.sla_capacity.capacity_gbps)
        return None

    def _resolve_vlan(self, device_obj, endpoint_objs, service_settings) -> Optional[int]:
        endpoint_settings = []
        for endpoint_obj in endpoint_objs:
            node = self.__settings_handler.get_endpoint_settings(device_obj, endpoint_obj)
            endpoint_settings.append(node.value if node is not None else None)
        # Explicit VLAN settings only: an L3 service's access VLAN ends at the routers.
        explicit = {k: v for k, v in service_settings.items() if k == 'vlan_id'}
        is_l2 = self.__service.service_type == ServiceTypeEnum.SERVICETYPE_L2NM
        access_points = self._access_point_settings() if is_l2 else []
        return resolve_vlan(endpoint_settings, explicit, access_points)

    def _slice_name(self) -> str:
        return self.__service.name or self.__service.service_id.service_uuid.uuid

    def _group_by_device(
        self, endpoints : List[Tuple[str, str, Optional[str]]]
    ) -> Dict[str, List[Tuple[int, str]]]:
        """device_uuid -> [(position in the request, endpoint_uuid)]"""
        groups : Dict[str, List[Tuple[int, str]]] = {}
        for position, endpoint in enumerate(endpoints):
            device_uuid, endpoint_uuid = get_device_endpoint_uuids(endpoint)
            groups.setdefault(device_uuid, []).append((position, endpoint_uuid))
        return groups

    def _configure(self, device_obj, json_config_rules : List[Dict]) -> None:
        del device_obj.device_config.config_rules[:]
        for json_config_rule in json_config_rules:
            device_obj.device_config.config_rules.append(ConfigRule(**json_config_rule))
        self.__task_executor.configure_device(device_obj)

    def _run_per_device(self, endpoints, compose) -> List[Union[bool, Exception]]:
        results : List[Union[bool, Exception]] = [True] * len(endpoints)
        for device_uuid, items in self._group_by_device(endpoints).items():
            try:
                device_obj = self.__task_executor.get_device(DeviceId(**json_device_id(device_uuid)))
                endpoint_objs = [get_endpoint_matching(device_obj, endpoint_uuid) for _, endpoint_uuid in items]
                json_config_rules = compose(device_obj, endpoint_objs)
                if len(json_config_rules) > 0:
                    self._configure(device_obj, json_config_rules)
            except Exception as e: # pylint: disable=broad-except
                LOGGER.exception('Unable to configure Ceragon device {:s}'.format(str(device_uuid)))
                for position, _ in items: results[position] = e
        return results

    # ── Endpoints ───────────────────────────────────────────────────────────

    @metered_subclass_method(METRICS_POOL)
    def SetEndpoint(
        self, endpoints : List[Tuple[str, str, Optional[str]]], connection_uuid : Optional[str] = None
    ) -> List[Union[bool, Exception]]:
        chk_type('endpoints', endpoints, list)
        if len(endpoints) == 0: return []

        service_uuid = self.__service.service_id.service_uuid.uuid
        service_settings = self._service_settings()
        bandwidth_mbps = resolve_bandwidth_mbps(service_settings, self._capacity_gbps())

        def compose(device_obj, endpoint_objs) -> List[Dict]:
            vlan_id = self._resolve_vlan(device_obj, endpoint_objs, service_settings)
            if vlan_id is None:
                LOGGER.info('Service {:s} is untagged on radio {:s}: default bridge'.format(
                    str(service_uuid), str(device_obj.name)))
            return compose_setup_rules(
                service_uuid, self._slice_name(), vlan_id, bandwidth_mbps,
                [endpoint_obj.name for endpoint_obj in endpoint_objs], service_settings)

        return self._run_per_device(endpoints, compose)

    @metered_subclass_method(METRICS_POOL)
    def DeleteEndpoint(
        self, endpoints : List[Tuple[str, str, Optional[str]]], connection_uuid : Optional[str] = None
    ) -> List[Union[bool, Exception]]:
        chk_type('endpoints', endpoints, list)
        if len(endpoints) == 0: return []

        service_uuid = self.__service.service_id.service_uuid.uuid
        service_settings = self._service_settings()

        def compose(device_obj, endpoint_objs) -> List[Dict]:
            vlan_id = self._resolve_vlan(device_obj, endpoint_objs, service_settings)
            return compose_teardown_rules(
                service_uuid, self._slice_name(), vlan_id, [endpoint_obj.name for endpoint_obj in endpoint_objs])

        return self._run_per_device(endpoints, compose)

    # ── Constraints and settings ────────────────────────────────────────────

    @metered_subclass_method(METRICS_POOL)
    def SetConstraint(self, constraints : List[Tuple[str, Any]]) -> List[Union[bool, Exception]]:
        chk_type('constraints', constraints, list)
        # The SLA capacity is read from the service when the endpoints are set.
        return [True for _ in range(len(constraints))]

    @metered_subclass_method(METRICS_POOL)
    def DeleteConstraint(self, constraints : List[Tuple[str, Any]]) -> List[Union[bool, Exception]]:
        chk_type('constraints', constraints, list)
        return [True for _ in range(len(constraints))]

    @metered_subclass_method(METRICS_POOL)
    def SetConfig(self, resources : List[Tuple[str, Any]]) -> List[Union[bool, Exception]]:
        chk_type('resources', resources, list)
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
        results = []
        for resource in resources:
            try:
                self.__settings_handler.delete(resource[0])
                results.append(True)
            except Exception as e: # pylint: disable=broad-except
                LOGGER.exception('Unable to DeleteConfig({:s})'.format(str(resource)))
                results.append(e)
        return results
