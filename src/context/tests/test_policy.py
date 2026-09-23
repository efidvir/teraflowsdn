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

import copy, grpc, pytest
from common.proto.context_pb2 import Empty
from common.proto.policy_pb2 import PolicyRuleId, PolicyRule
from context.client.ContextClient import ContextClient
from context.service.database.uuids.PolicuRule import policyrule_get_uuid
from .Objects import POLICYRULE, POLICYRULE_ID, POLICYRULE_NAME

@pytest.mark.depends(on=['context/tests/test_connection.py::test_connection'])
def test_policy(context_client : ContextClient):

    # ----- Get when the object does not exist -------------------------------------------------------------------------
    policyrule_id = PolicyRuleId(**POLICYRULE_ID)
    policyrule_uuid = policyrule_get_uuid(policyrule_id, allow_random=False)

    with pytest.raises(grpc.RpcError) as e:
        context_client.GetPolicyRule(policyrule_id)
    assert e.value.code() == grpc.StatusCode.NOT_FOUND
    MSG = 'PolicyRule({:s}) not found; policyrule_uuid generated was: {:s}'
    assert e.value.details() == MSG.format(POLICYRULE_NAME, policyrule_uuid)

    # ----- List when the object does not exist ------------------------------------------------------------------------
    response = context_client.ListPolicyRuleIds(Empty())
    assert len(response.policyRuleIdList) == 0

    response = context_client.ListPolicyRules(Empty())
    assert len(response.policyRules) == 0

    # ----- Create the object ------------------------------------------------------------------------------------------
    response = context_client.SetPolicyRule(PolicyRule(**POLICYRULE))
    assert response.uuid.uuid == policyrule_uuid

    # ----- Get when the object exists ---------------------------------------------------------------------------------
    response = context_client.GetPolicyRule(PolicyRuleId(**POLICYRULE_ID))
    policy_basic = response.device.policyRuleBasic
    assert policy_basic.policyRuleId.uuid.uuid == policyrule_uuid
    assert policy_basic.policyRulePriority == 1
    assert len(policy_basic.policyRuleKpiList) == 1
    assert policy_basic.policyRuleKpiList[0].policyRuleKpiUuid.uuid == 'my-kpi-id-1'

    # ----- List when the object exists --------------------------------------------------------------------------------
    response = context_client.ListPolicyRuleIds(Empty())
    assert len(response.policyRuleIdList) == 1
    assert response.policyRuleIdList[0].uuid.uuid == policyrule_uuid

    response = context_client.ListPolicyRules(Empty())
    assert len(response.policyRules) == 1
    policy_basic = response.policyRules[0].device.policyRuleBasic
    assert policy_basic.policyRuleId.uuid.uuid == policyrule_uuid
    assert policy_basic.policyRulePriority == 1
    assert len(policy_basic.policyRuleKpiList) == 1
    assert policy_basic.policyRuleKpiList[0].policyRuleKpiUuid.uuid == 'my-kpi-id-1'

    # ----- Update the object ------------------------------------------------------------------------------------------
    new_policy_priority = 100
    new_policy_list_kpi_id = ['my-kpi-id-1', 'my-kpi-id-2']
    POLICYRULE_UPDATED = copy.deepcopy(POLICYRULE)
    POLICYRULE_UPDATED['device']['policyRuleBasic']['policyRulePriority'] = new_policy_priority
    POLICYRULE_UPDATED['device']['policyRuleBasic']['policyRuleKpiList'] = [
        {'policyRuleKpiUuid': {'uuid': kpi_id}}
        for kpi_id in new_policy_list_kpi_id
    ]
    response = context_client.SetPolicyRule(PolicyRule(**POLICYRULE_UPDATED))
    assert response.uuid.uuid == policyrule_uuid

    # ----- Get when the object is modified ----------------------------------------------------------------------------
    response = context_client.GetPolicyRule(PolicyRuleId(**POLICYRULE_ID))
    assert response.device.policyRuleBasic.policyRuleId.uuid.uuid == policyrule_uuid

    # ----- List when the object is modified ---------------------------------------------------------------------------
    response = context_client.ListPolicyRuleIds(Empty())
    assert len(response.policyRuleIdList) == 1
    assert response.policyRuleIdList[0].uuid.uuid == policyrule_uuid

    response = context_client.ListPolicyRules(Empty())
    assert len(response.policyRules) == 1
    policy_basic = response.policyRules[0].device.policyRuleBasic
    assert policy_basic.policyRuleId.uuid.uuid == policyrule_uuid
    assert policy_basic.policyRulePriority == new_policy_priority
    assert len(policy_basic.policyRuleKpiList) == 2
    for i,kpi_id in enumerate(new_policy_list_kpi_id):
        assert policy_basic.policyRuleKpiList[i].policyRuleKpiUuid.uuid == kpi_id

    # ----- Remove the object ------------------------------------------------------------------------------------------
    context_client.RemovePolicyRule(PolicyRuleId(**POLICYRULE_ID))

    # ----- List after deleting the object -----------------------------------------------------------------------------
    response = context_client.ListPolicyRuleIds(Empty())
    assert len(response.policyRuleIdList) == 0

    response = context_client.ListPolicyRules(Empty())
    assert len(response.policyRules) == 0
