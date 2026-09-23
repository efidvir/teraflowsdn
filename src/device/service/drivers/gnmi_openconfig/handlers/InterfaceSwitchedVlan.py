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
from typing import Any, Dict, List, Tuple
from ._Handler import _Handler
from .Tools import get_str
from .YangHandler import YangHandler

LOGGER = logging.getLogger(__name__)

RE_IF_SWITCHED_VLAN = re.compile(r'^/interface\[(?:name=)?([^\]]+)\]/ethernet/switched-vlan$')

class InterfaceSwitchedVlanHandler(_Handler):
    def get_resource_key(self) -> str: return '/interface/ethernet/switched-vlan'
    def get_path(self) -> str: return '/openconfig-interfaces:interfaces/interface/ethernet/switched-vlan'

    def _get_interface_name(self, resource_key : str, resource_value : Dict) -> str:
        if 'name' in resource_value:
            return get_str(resource_value, 'name')
        if 'interface' in resource_value:
            return get_str(resource_value, 'interface')
        match = RE_IF_SWITCHED_VLAN.match(resource_key)
        if match is None:
            MSG = 'Interface name not found in resource_key={:s} resource_value={:s}'
            raise Exception(MSG.format(str(resource_key), str(resource_value)))
        return match.groups()[0]

    def _normalize_config(self, resource_value : Dict) -> Dict[str, Any]:
        config = resource_value.get('config')
        if isinstance(config, dict):
            return config

        interface_mode = resource_value.get('interface-mode', resource_value.get('interface_mode'))
        if interface_mode is None:
            raise Exception('interface-mode is required for switched-vlan config')
        interface_mode = str(interface_mode).upper()

        config = {'interface-mode': interface_mode}
        if interface_mode == 'ACCESS':
            access_vlan = resource_value.get('access-vlan', resource_value.get('access_vlan'))
            if access_vlan is None:
                raise Exception('access-vlan is required for ACCESS mode')
            config['access-vlan'] = int(access_vlan)
        elif interface_mode == 'TRUNK':
            native_vlan = resource_value.get('native-vlan', resource_value.get('native_vlan', 1))
            config['native-vlan'] = int(native_vlan)
            trunk_vlans = resource_value.get('trunk-vlans', resource_value.get('trunk_vlans'))
            if trunk_vlans is None:
                trunk_vlan = resource_value.get('trunk-vlan', resource_value.get('trunk_vlan'))
                trunk_vlans = [trunk_vlan] if trunk_vlan is not None else []
            if not isinstance(trunk_vlans, list):
                trunk_vlans = [trunk_vlans]
            config['trunk-vlans'] = [int(vlan) for vlan in trunk_vlans if vlan is not None]
        else:
            raise Exception('Unsupported interface-mode: {:s}'.format(str(interface_mode)))

        return config

    def compose(
        self, resource_key : str, resource_value : Dict, yang_handler : YangHandler, delete : bool = False
    ) -> Tuple[str, str]:
        if_name = self._get_interface_name(resource_key, resource_value)
        str_path = '/interfaces/interface[name={:s}]/ethernet/switched-vlan'.format(if_name)
        if delete:
            return str_path, json.dumps({})

        config = self._normalize_config(resource_value)
        str_data = json.dumps({'config': config})
        return str_path, str_data

    def parse(
        self, json_data : Dict, yang_handler : YangHandler
    ) -> List[Tuple[str, Dict[str, Any]]]:
        json_data_valid = yang_handler.parse_to_dict(
            '/openconfig-interfaces:interfaces', json_data, fmt='json', strict=False
        )

        entries = []
        for interface in json_data_valid.get('interfaces', {}).get('interface', []):
            interface_name = interface['name']
            ethernet = interface.get('ethernet', {})
            switched_vlan = ethernet.get('switched-vlan')
            if switched_vlan is None:
                continue
            entry_key = '/interface[{:s}]/ethernet/switched-vlan'.format(interface_name)
            entry_value = {}
            if 'config' in switched_vlan:
                entry_value['config'] = switched_vlan['config']
            if 'state' in switched_vlan:
                entry_value['state'] = switched_vlan['state']
            entries.append((entry_key, entry_value))
        return entries
