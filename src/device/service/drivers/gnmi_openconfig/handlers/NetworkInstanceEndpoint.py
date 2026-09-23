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
from typing import Any, Dict, List, Tuple
from ._Handler import _Handler
from .Tools import get_int, get_str
from .YangHandler import YangHandler

LOGGER = logging.getLogger(__name__)

class NetworkInstanceEndpointHandler(_Handler):
    def get_resource_key(self) -> str: return '/network_instance/connection_point/endpoint'
    def get_path(self) -> str:
        return '/openconfig-network-instance:network-instances/network-instance/connection-points/connection-point/endpoints/endpoint'

    def compose(
        self, resource_key : str, resource_value : Dict, yang_handler : YangHandler, delete : bool = False
    ) -> Tuple[str, str]:
        ni_name = get_str(resource_value, 'name')
        cp_id   = get_str(resource_value, 'connection_point_id')
        ep_id   = get_str(resource_value, 'endpoint_id')
        ep_type = get_str(resource_value, 'type')
        precedence = get_int(resource_value, 'precedence')

        str_path = (
            '/network-instances/network-instance[name={:s}]/connection-points/connection-point'
            '[connection-point-id={:s}]/endpoints/endpoint[endpoint-id={:s}]'
        ).format(ni_name, cp_id, ep_id)
        if delete:
            return str_path, json.dumps({})

        if ep_type is not None and ':' not in ep_type:
            ep_type = 'openconfig-network-instance-types:{:s}'.format(ep_type)

        yang_nis : Any = yang_handler.get_data_path('/openconfig-network-instance:network-instances')
        path_ep_base = (
            'network-instance[name="{:s}"]/connection-points/connection-point[connection-point-id="{:s}"]'
            '/endpoints/endpoint[endpoint-id="{:s}"]'
        ).format(ni_name, cp_id, ep_id)
        yang_nis.create_path('{:s}/config/endpoint-id'.format(path_ep_base), ep_id)
        if ep_type is not None:
            yang_nis.create_path('{:s}/config/type'.format(path_ep_base), ep_type)
        if precedence is not None:
            yang_nis.create_path('{:s}/config/precedence'.format(path_ep_base), precedence)

        if ep_type and ep_type.endswith('LOCAL'):
            if_name = get_str(resource_value, 'interface')
            sif_index = get_int(resource_value, 'subinterface', 0)
            if if_name is not None:
                yang_nis.create_path('{:s}/local/config/interface'.format(path_ep_base), if_name)
                yang_nis.create_path('{:s}/local/config/subinterface'.format(path_ep_base), sif_index)
            site_id = get_int(resource_value, 'site_id')
            if site_id is not None:
                yang_nis.create_path('{:s}/local/config/site-id'.format(path_ep_base), site_id)
        elif ep_type and ep_type.endswith('REMOTE'):
            remote_system = get_str(resource_value, 'remote_system')
            vc_id = get_int(resource_value, 'virtual_circuit_id')
            if remote_system is not None:
                yang_nis.create_path('{:s}/remote/config/remote-system'.format(path_ep_base), remote_system)
            if vc_id is not None:
                yang_nis.create_path(
                    '{:s}/remote/config/virtual-circuit-identifier'.format(path_ep_base), vc_id
                )
            site_id = get_int(resource_value, 'site_id')
            if site_id is not None:
                yang_nis.create_path('{:s}/remote/config/site-id'.format(path_ep_base), site_id)

        yang_ep : Any = yang_nis.find_path(path_ep_base)
        json_data = json.loads(yang_ep.print_mem('json'))
        json_data = json_data['openconfig-network-instance:endpoint'][0]
        return str_path, json.dumps(json_data)

    def parse(
        self, json_data : Dict, yang_handler : YangHandler
    ) -> List[Tuple[str, Dict[str, Any]]]:
        LOGGER.debug('[parse] json_data = %s', json.dumps(json_data))
        return []
