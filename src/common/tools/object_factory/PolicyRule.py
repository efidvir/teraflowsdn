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

import logging
from typing import Dict, List, Optional
from common.proto.policy_pb2 import PolicyRuleStateEnum

LOGGER = logging.getLogger(__name__)

def json_policyrule_id(policyrule_uuid : str) -> Dict:
    return {'uuid': {'uuid': policyrule_uuid}}

def json_policyrule(
    policyrule_uuid : str,
    state : PolicyRuleStateEnum = PolicyRuleStateEnum.POLICY_UNDEFINED, state_message : str = '',
    priority : int = 1, action_list : List[Dict] = [], list_kpi_id : List[str] = list(),
    service_id : Optional[Dict] = None, device_id_list : List[Dict] = []
) -> Dict:
    basic = {
        'policyRuleId': json_policyrule_id(policyrule_uuid),
        'policyRuleState': {
            'policyRuleState': state,
            'policyRuleStateMessage': state_message,
        },
        'policyRulePriority': priority,
        'actionList': action_list,
        'policyRuleKpiList': [
            {'policyRuleKpiUuid': {'uuid': kpi_id}}
            for kpi_id in list_kpi_id
        ],
    }

    result = {}
    if service_id is not None:
        policyrule_type = 'service'
        result[policyrule_type] = {'policyRuleBasic': basic}
        result[policyrule_type]['serviceId'] = service_id
    else:
        policyrule_type = 'device'
        result[policyrule_type] = {'policyRuleBasic': basic}

    result[policyrule_type]['deviceList'] = device_id_list
    return result
