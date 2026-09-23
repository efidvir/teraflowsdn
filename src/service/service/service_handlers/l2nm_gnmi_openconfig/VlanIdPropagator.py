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

import json, logging
from typing import List, Optional, Tuple
from common.DeviceTypes import DeviceTypeEnum
from .ConfigRuleComposer import ConfigRuleComposer

LOGGER = logging.getLogger(__name__)

class VlanIdPropagator:
    def __init__(self, config_rule_composer : ConfigRuleComposer) -> None:
        self._config_rule_composer = config_rule_composer
        self._router_types = {
            DeviceTypeEnum.PACKET_ROUTER.value,
            DeviceTypeEnum.EMULATED_PACKET_ROUTER.value,
            DeviceTypeEnum.PACKET_POP.value,
            DeviceTypeEnum.PACKET_RADIO_ROUTER.value,
            DeviceTypeEnum.EMULATED_PACKET_RADIO_ROUTER.value,
        }

    def _is_router_device(self, device) -> bool:
        return device.objekt is not None and device.objekt.device_type in self._router_types

    def compose(self, connection_hop_list : List[Tuple[str, str, Optional[str]]]) -> None:
        link_endpoints = self._compute_link_endpoints(connection_hop_list)
        LOGGER.debug('link_endpoints = {:s}'.format(str(link_endpoints)))

        self._propagate_vlan_id(link_endpoints)
        LOGGER.debug('config_rule_composer = {:s}'.format(json.dumps(self._config_rule_composer.dump())))

    def _compute_link_endpoints(
        self, connection_hop_list : List[Tuple[str, str, Optional[str]]]
    ) -> List[Tuple[Tuple[str, str, Optional[str]], Tuple[str, str, Optional[str]]]]:
        # In some cases connection_hop_list might contain repeated endpoints, remove them here.
        added_connection_hops = set()
        filtered_connection_hop_list = list()
        for connection_hop in connection_hop_list:
            if connection_hop in added_connection_hops: continue
            filtered_connection_hop_list.append(connection_hop)
            added_connection_hops.add(connection_hop)
        connection_hop_list = filtered_connection_hop_list

        # In some cases connection_hop_list first and last items might be internal endpoints of
        # devices instead of link endpoints. Filter those endpoints not reaching a new device.
        if len(connection_hop_list) > 2 and connection_hop_list[0][0] == connection_hop_list[1][0]:
            # same device on first 2 endpoints
            connection_hop_list = connection_hop_list[1:]
        if len(connection_hop_list) > 2 and connection_hop_list[-1][0] == connection_hop_list[-2][0]:
            # same device on last 2 endpoints
            connection_hop_list = connection_hop_list[:-1]

        num_connection_hops = len(connection_hop_list)
        if num_connection_hops % 2 != 0: raise Exception('Number of connection hops must be even')
        if num_connection_hops < 4: raise Exception('Number of connection hops must be >= 4')

        it_connection_hops = iter(connection_hop_list)
        return list(zip(it_connection_hops, it_connection_hops))

    def _propagate_vlan_id(
        self, link_endpoints_list : List[Tuple[Tuple[str, str, Optional[str]], Tuple[str, str, Optional[str]]]]
    ) -> None:
        for link_endpoints in link_endpoints_list:
            device_endpoint_a, device_endpoint_b = link_endpoints

            device_uuid_a, endpoint_uuid_a = device_endpoint_a[0:2]
            device_a   = self._config_rule_composer.get_device(device_uuid_a)
            endpoint_a = device_a.get_endpoint(endpoint_uuid_a)

            device_uuid_b, endpoint_uuid_b = device_endpoint_b[0:2]
            device_b   = self._config_rule_composer.get_device(device_uuid_b)
            endpoint_b = device_b.get_endpoint(endpoint_uuid_b)

            if self._is_router_device(device_a) and self._is_router_device(device_b):
                endpoint_a.set_force_trunk()
                endpoint_b.set_force_trunk()
