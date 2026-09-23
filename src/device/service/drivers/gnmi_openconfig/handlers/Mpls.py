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
from .Tools import get_int, get_str
from .YangHandler import YangHandler

LOGGER = logging.getLogger(__name__)

RE_MPLS_INTERFACE = re.compile(r'^/mpls/interface\[([^\]]+)\]$')
DEFAULT_NETWORK_INSTANCE = 'default'

class MplsHandler(_Handler):
    def get_resource_key(self) -> str: return '/mpls'
    def get_path(self) -> str:
        return '/openconfig-network-instance:network-instances/network-instance/mpls'

    def compose(
        self, resource_key : str, resource_value : Dict, yang_handler : YangHandler, delete : bool = False
    ) -> Tuple[str, str]:
        """
        Compose MPLS (global or per-interface) configuration.
        - Global: set LDP router-id (lsr-id) and optional hello timers.
        - Interface: set LDP interface-id and optional hello timers.
        """
        ni_name = get_str(resource_value, 'network_instance', DEFAULT_NETWORK_INSTANCE)
        ni_type = get_str(resource_value, 'network_instance_type')
        if ni_type is None and ni_name == DEFAULT_NETWORK_INSTANCE:
            ni_type = 'openconfig-network-instance-types:DEFAULT_INSTANCE'

        yang_nis : Any = yang_handler.get_data_path('/openconfig-network-instance:network-instances')
        yang_ni : Any = yang_nis.create_path('network-instance[name="{:s}"]'.format(ni_name))
        yang_ni.create_path('config/name', ni_name)
        if ni_type is not None:
            yang_ni.create_path('config/type', ni_type)

        match_if = RE_MPLS_INTERFACE.match(resource_key)
        if delete:
            if match_if:
                if_name = match_if.group(1)
                str_path = (
                    '/network-instances/network-instance[name={:s}]/mpls/signaling-protocols/ldp'
                    '/interface-attributes/interfaces/interface[interface-id={:s}]'
                ).format(ni_name, if_name)
            else:
                str_path = '/network-instances/network-instance[name={:s}]/mpls'.format(ni_name)
            return str_path, json.dumps({})

        if match_if:
            if_name = match_if.group(1)
            hello_interval = get_int(resource_value, 'hello_interval')
            hello_holdtime = get_int(resource_value, 'hello_holdtime')

            path_if_base = (
                'mpls/signaling-protocols/ldp/interface-attributes/interfaces'
                '/interface[interface-id="{:s}"]/config'
            ).format(if_name)
            yang_ni.create_path('{:s}/interface-id'.format(path_if_base), if_name)
            if hello_interval is not None:
                yang_ni.create_path('{:s}/hello-interval'.format(path_if_base), hello_interval)
            if hello_holdtime is not None:
                yang_ni.create_path('{:s}/hello-holdtime'.format(path_if_base), hello_holdtime)

            yang_if : Any = yang_ni.find_path(
                'mpls/signaling-protocols/ldp/interface-attributes/interfaces'
                '/interface[interface-id="{:s}"]'.format(if_name)
            )

            str_path = (
                '/network-instances/network-instance[name={:s}]/mpls/signaling-protocols/ldp'
                '/interface-attributes/interfaces/interface[interface-id={:s}]'
            ).format(ni_name, if_name)
            json_data = json.loads(yang_if.print_mem('json'))
            json_data = json_data['openconfig-network-instance:interface'][0]
            str_data = json.dumps(json_data)
            return str_path, str_data

        # Global LDP configuration
        ldp_cfg = resource_value.get('ldp', resource_value)
        lsr_id = get_str(ldp_cfg, 'lsr_id')
        hello_interval = get_int(ldp_cfg, 'hello_interval')
        hello_holdtime = get_int(ldp_cfg, 'hello_holdtime')

        if lsr_id is not None:
            yang_ni.create_path('mpls/signaling-protocols/ldp/global/config/lsr-id', lsr_id)
        if hello_interval is not None:
            yang_ni.create_path(
                'mpls/signaling-protocols/ldp/interface-attributes/config/hello-interval', hello_interval
            )
        if hello_holdtime is not None:
            yang_ni.create_path(
                'mpls/signaling-protocols/ldp/interface-attributes/config/hello-holdtime', hello_holdtime
            )

        yang_ldp : Any = yang_ni.find_path('mpls/signaling-protocols/ldp')

        str_path = '/network-instances/network-instance[name={:s}]/mpls/signaling-protocols/ldp'.format(ni_name)
        json_data = json.loads(yang_ldp.print_mem('json'))
        json_data = json_data['openconfig-network-instance:ldp']
        str_data = json.dumps(json_data)
        return str_path, str_data

    def parse(
        self, json_data : Dict, yang_handler : YangHandler
    ) -> List[Tuple[str, Dict[str, Any]]]:
        LOGGER.debug('[parse] json_data = %s', json.dumps(json_data))
        # Not required for current tests (L2VPN validation focuses on SetConfig).
        return []
