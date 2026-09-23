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

from common.tools.object_factory.ConfigRule import json_config_rule_delete, json_config_rule_set
from common.tools.object_factory.Device import (
    json_device_connect_rules, json_device_id, json_device_tapi_disabled)

DEVICE_TAPI_UUID    = 'DEVICE-TAPI'     # populate 'device-uuid' of the TAPI server
DEVICE_TAPI_ADDRESS = '0.0.0.0'         # populate 'address' of the TAPI server
DEVICE_TAPI_PORT    = 4900              # populate 'port' of the TAPI server
DEVICE_TAPI_TIMEOUT = 120               # populate 'timeout' of the TAPI server

DEVICE_TAPI_ID = json_device_id(DEVICE_TAPI_UUID)
DEVICE_TAPI    = json_device_tapi_disabled(DEVICE_TAPI_UUID)

DEVICE_TAPI_CONNECT_RULES = json_device_connect_rules(DEVICE_TAPI_ADDRESS, DEVICE_TAPI_PORT, {
    'timeout' : DEVICE_TAPI_TIMEOUT,
})

DEVICE_TAPI_CONFIG_RULES = [
    json_config_rule_set('node_4_port_16-input_to_node_2_port_17-output', {
        'uuid'                    : 'service-uuid',     # populate 'service-uuid' of the service to test
        'input_sip'               : 'input-sip-uuid',   # populate 'input-sip-uuid' of the service to test
        'output_sip'              : 'output-sip-uuid',  # populate 'output-sip-uuid' of the service to test
        'capacity_unit'           : 'GHz',              # populate 'capacity-unit' of the service to test
        'capacity_value'          : 1,                  # populate 'capacity-value' of the service to test
        'direction'               : 'UNIDIRECTIONAL',   # populate 'direction' of the service to test
        'layer_protocol_name'     : 'PHOTONIC_MEDIA',
        'layer_protocol_qualifier': 'tapi-photonic-media:PHOTONIC_LAYER_QUALIFIER_NMC',
    })
]

DEVICE_TAPI_DECONFIG_RULES = [
    json_config_rule_delete('node_4_port_16-input_to_node_2_port_17-output', {
        'uuid': 'service-uuid'                          # populate 'service-uuid' of the service to test
    })
]
