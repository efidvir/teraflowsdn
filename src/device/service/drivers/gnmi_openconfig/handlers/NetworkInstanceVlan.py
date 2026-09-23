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
from typing import Any, Dict, List, Tuple, Union
from ._Handler import _Handler
from .Tools import get_int, get_str
from .YangHandler import YangHandler

LOGGER = logging.getLogger(__name__)

class NetworkInstanceVlanHandler(_Handler):
    def get_resource_key(self) -> str: return '/network_instance/vlan'
    def get_path(self) -> str:
        return '/openconfig-network-instance:network-instances/network-instance/vlans/vlan'

    def compose(
        self, resource_key : str, resource_value : Dict, yang_handler : YangHandler, delete : bool = False
    ) -> Tuple[str, str]:
        ni_name = get_str(resource_value, 'name', 'default')
        vlan_id = get_int(resource_value, 'vlan_id')
        vlan_name = get_str(resource_value, 'vlan_name')
        str_path = '/network-instances/network-instance[name={:s}]/vlans/vlan[vlan-id={:d}]'.format(
            ni_name, vlan_id
        )
        if delete:
            yang_nis : Any = yang_handler.get_data_path('/openconfig-network-instance:network-instances')
            yang_vlan = yang_nis.find_path('network-instance[name="{:s}"]/vlans/vlan[vlan-id="{:d}"]'.format(
                ni_name, vlan_id))
            if yang_vlan is not None:
                yang_vlan.unlink()
                yang_vlan.free()
            return str_path, json.dumps({})

        yang_nis : Any = yang_handler.get_data_path('/openconfig-network-instance:network-instances')
        yang_ni : Any = yang_nis.create_path('network-instance[name="{:s}"]'.format(ni_name))
        yang_ni.create_path('config/name', ni_name)
        if ni_name == 'default':
            yang_ni.create_path('config/type', 'openconfig-network-instance-types:DEFAULT_INSTANCE')

        yang_vlans : Any = yang_ni.create_path('vlans')
        yang_vlan : Any = yang_vlans.create_path('vlan[vlan-id="{:d}"]'.format(vlan_id))
        yang_vlan.create_path('config/vlan-id', vlan_id)
        if vlan_name is not None:
            yang_vlan.create_path('config/name', vlan_name)

        json_data = json.loads(yang_vlan.print_mem('json'))
        json_data = json_data['openconfig-network-instance:vlan'][0]
        return str_path, json.dumps(json_data)

    def parse(
        self, json_data : Dict, yang_handler : YangHandler
    ) -> List[Tuple[str, Dict[str, Any]]]:
        LOGGER.debug('[parse] json_data = %s', json.dumps(json_data))
        return []
