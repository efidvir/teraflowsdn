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
from .Tools import get_str
from .YangHandler import YangHandler

LOGGER = logging.getLogger(__name__)

class NetworkInstanceConnectionPointHandler(_Handler):
    def get_resource_key(self) -> str: return '/network_instance/connection_point'
    def get_path(self) -> str:
        return '/openconfig-network-instance:network-instances/network-instance/connection-points/connection-point'

    def compose(
        self, resource_key : str, resource_value : Dict, yang_handler : YangHandler, delete : bool = False
    ) -> Tuple[str, str]:
        ni_name = get_str(resource_value, 'name')
        cp_id   = get_str(resource_value, 'connection_point_id')

        str_path = (
            '/network-instances/network-instance[name={:s}]/connection-points'
            '/connection-point[connection-point-id={:s}]'
        ).format(ni_name, cp_id)
        if delete:
            return str_path, json.dumps({})

        yang_nis : Any = yang_handler.get_data_path('/openconfig-network-instance:network-instances')
        path_cp_base = (
            'network-instance[name="{:s}"]/connection-points'
            '/connection-point[connection-point-id="{:s}"]'
        ).format(ni_name, cp_id)
        yang_nis.create_path('{:s}/config/connection-point-id'.format(path_cp_base), cp_id)

        yang_cp : Any = yang_nis.find_path(path_cp_base)
        json_data = json.loads(yang_cp.print_mem('json'))
        json_data = json_data['openconfig-network-instance:connection-point'][0]
        return str_path, json.dumps(json_data)

    def parse(
        self, json_data : Dict, yang_handler : YangHandler
    ) -> List[Tuple[str, Dict[str, Any]]]:
        LOGGER.debug('[parse] json_data = %s', json.dumps(json_data))
        return []
