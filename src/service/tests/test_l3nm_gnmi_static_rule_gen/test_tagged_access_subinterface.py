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

import json
import importlib.util
from pathlib import Path
from types import SimpleNamespace


MODULE_PATH = (
    Path(__file__).resolve().parents[3]
    / 'service'
    / 'service'
    / 'service_handlers'
    / 'l3nm_gnmi_openconfig'
    / 'ConfigRuleComposer.py'
)
MODULE_SPEC = importlib.util.spec_from_file_location('ConfigRuleComposer', MODULE_PATH)
assert MODULE_SPEC is not None
assert MODULE_SPEC.loader is not None
CONFIG_RULE_COMPOSER = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(CONFIG_RULE_COMPOSER)
EndpointComposer = CONFIG_RULE_COMPOSER.EndpointComposer


def test_tagged_access_preserves_subinterface_index() -> None:
    endpoint = EndpointComposer('endpoint-uuid')
    endpoint.objekt = SimpleNamespace(name='Ethernet11')
    endpoint.ipv4_address = '172.17.1.1'
    endpoint.ipv4_prefix_len = 24
    endpoint.sub_interface_index = 0
    endpoint.explicit_vlan_ids = {125}

    config_rules = endpoint.get_config_rules(
        'default', service_vlan_id=125, access_vlan_tagged=False, delete=False
    )

    assert len(config_rules) == 1
    config_rule = config_rules[0]
    assert config_rule['custom']['resource_key'] == '/interface[Ethernet11]/subinterface[0]'

    resource_value = json.loads(config_rule['custom']['resource_value'])
    assert resource_value['index'] == 0
    assert resource_value['vlan_id'] == 125
