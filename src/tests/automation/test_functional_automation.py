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

import json, logging, os, uuid

from automation.client.AutomationClient import AutomationClient
from common.proto.analytics_frontend_pb2 import (
    AnalyzerId, AnalyzerOperationMode,
)
from common.proto.automation_pb2 import ZSMCreateRequest
from common.proto.context_pb2 import (
    ContextId, ServiceId, ServiceList, ServiceStatusEnum,
)
from common.proto.kpi_manager_pb2 import (
    KpiDescriptorFilter, KpiDescriptorList, KpiId,
)
from common.proto.policy_action_pb2 import (
    PolicyRuleAction, PolicyRuleActionEnum,
)
from common.proto.policy_pb2 import PolicyRuleKpiId, PolicyRuleStateEnum
from common.tools.descriptor.Loader import (
    DescriptorLoader, check_descriptor_load_results,
)
from context.client.ContextClient import ContextClient
from device.client.DeviceClient import DeviceClient
from kpi_manager.client.KpiManagerClient import KpiManagerClient
from service.client.ServiceClient import ServiceClient
from tests.tools.test_tools_p4 import *

from .Fixtures import (
    automation_client, context_client, device_client, kpi_manager_client,
    service_client,
)  # pylint: disable=unused-import

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

TEST_PATH = os.path.join(
    os.path.dirname(
        os.path.abspath(__file__)
    ) + '/descriptors')
assert os.path.exists(TEST_PATH), "Invalid path to tests"

DESC_FILE_SERVICE_AUTOMATION = os.path.join(TEST_PATH, 'automation.json')
assert os.path.exists(DESC_FILE_SERVICE_AUTOMATION),\
    "Invalid path to the automation descriptor"

def test_service_zsm_create(
    context_client : ContextClient, # pylint: disable=redefined-outer-name
    device_client  : DeviceClient,  # pylint: disable=redefined-outer-name
    service_client : ServiceClient,  # pylint: disable=redefined-outer-name
    automation_client : AutomationClient,  # pylint: disable=redefined-outer-name
    kpi_manager_client : KpiManagerClient
) -> None:

    # Load service
    descriptor_loader = DescriptorLoader(
        descriptors_file=DESC_FILE_SERVICE_AUTOMATION,
        context_client=context_client, device_client=device_client, service_client=service_client
    )
    results = descriptor_loader.process()
    check_descriptor_load_results(results, descriptor_loader)

    data = None
    with open(DESC_FILE_SERVICE_AUTOMATION) as f:
        data = json.load(f)

    loaded_request : ZSMCreateRequest = ZSMCreateRequest(**data) # type: ignore
    assert loaded_request

    # Mark important service IDs
    context_uuid = loaded_request.target_service_id.context_id.context_uuid.uuid
    target_service_uuid = loaded_request.target_service_id.service_uuid.uuid
    telemetry_service_uuid = loaded_request.telemetry_service_id.service_uuid.uuid

    # Check that the associated services are valid
    try:
        _check_context(context_client, context_uuid, target_service_uuid, telemetry_service_uuid)
    except Exception as ex:
        raise(ex)

    # Add important information in the request
    loaded_request = _zsm_create_request(loaded_request, kpi_manager_client)

    # Invoke Automation
    automation_client.ZSMCreate(loaded_request)

def _check_context(context_client, context_uuid : str, target_service_uuid : str, telemetry_service_uuid : str):
    context_id : ContextId = ContextId() # type: ignore
    context_id.context_uuid.uuid = context_uuid

    # Get the available services
    service_list : ServiceList = context_client.ListServices(context_id) # type: ignore
    for service in service_list.services:
        service_id = service.service_id
        assert service_id

        ctx_uuid = service_id.context_id.context_uuid.uuid
        assert ctx_uuid == context_uuid, "Context UUID does not match"

        service_uuid = service_id.service_uuid.uuid
        assert service_uuid, "Invalid service UUID"

        if service_uuid not in [target_service_uuid, telemetry_service_uuid]:
            continue

        # The service we care about must be active
        assert service.service_status.service_status == ServiceStatusEnum.SERVICESTATUS_ACTIVE

def _zsm_create_request(request : ZSMCreateRequest, kpi_manager_client : KpiManagerClient) -> ZSMCreateRequest: # type: ignore
    LOGGER.info("Preparing the ZSM request") 
    telemetry_service_obj = ServiceId()
    telemetry_service_obj.service_uuid.uuid = request.telemetry_service_id.service_uuid.uuid

    ### Analyzer
    # Analyzer requires an ID
    if not request.analyzer.HasField("analyzer_id"):
        request.analyzer.analyzer_id.analyzer_id.uuid = str(uuid.uuid4())

    # Validate the inserted KPIs
    for kpi_id in request.analyzer.input_kpi_ids:
      create_kpi_filter_request = KpiDescriptorFilter()
      create_kpi_filter_request.kpi_id.append(kpi_id)
      create_kpi_filter_request.service_id.append(telemetry_service_obj)
      desc_list = kpi_manager_client.SelectKpiDescriptor(create_kpi_filter_request)
      assert isinstance(desc_list, KpiDescriptorList)
      for kpi in desc_list.kpi_descriptor_list:
        LOGGER.info(f"Validated KPI:\n{kpi}")

    ### Policy
    assert request.policy.policyRuleBasic, "Policy must at least have a basic rule body"
    # Policy requires an ID
    if not request.policy.policyRuleBasic.HasField("policyRuleId"):
        request.policy.policyRuleBasic.policyRuleId.uuid.uuid = str(uuid.uuid4())
    # Policy requires a state
    if not request.policy.policyRuleBasic.HasField("policyRuleState"):
        request.policy.policyRuleBasic.policyRuleState.policyRuleState = PolicyRuleStateEnum.POLICY_UNDEFINED
        request.policy.policyRuleBasic.policyRuleState.policyRuleStateMessage = "About to insert policy"
    # Link policy with the output KPI
    for kpi_id in request.analyzer.output_kpi_ids:
        rule_kpi = PolicyRuleKpiId()
        rule_kpi.policyRuleKpiUuid.uuid = kpi_id.kpi_id.uuid
        request.policy.policyRuleBasic.policyRuleKpiList.append(rule_kpi)
    
    # Policy requires a priority
    request.policy.policyRuleBasic.policyRulePriority = 1

    return request

def _static_zsm_create_request():
    context_uuid = "43813baf-195e-5da6-af20-b3d0922e71a7"
    target_service_uuid = "66d498ad-5d94-5d90-8cb4-861e30689c64"
    telemetry_service_uuid = "db73d789-4abc-5514-88bb-e21f7e31d36a"
    kpi_input_uuid = "b7006457-610b-4d76-b3fe-7ef36f1d4f49"
    kpi_output_uuid = "c45b09d8-c84a-45d8-b4c2-9fa9902d157d"

    request : ZSMCreateRequest = ZSMCreateRequest() # type: ignore

    # Services
    request.target_service_id.service_uuid.uuid = target_service_uuid
    request.target_service_id.context_id.context_uuid.uuid = context_uuid
    request.telemetry_service_id.service_uuid.uuid = telemetry_service_uuid
    request.telemetry_service_id.context_id.context_uuid.uuid = context_uuid

    # Analyzer
    request.analyzer.analyzer_id.analyzer_id.uuid = str(uuid.uuid4())
    request.analyzer.operation_mode = AnalyzerOperationMode.ANALYZEROPERATIONMODE_STREAMING
    threshold_dict = {
        "task_type": "AggregationHandler",
        "task_parameter": [
            {"avg": [0, 2500]}
        ]
    }
    request.analyzer.parameters["thresholds"] = json.dumps(threshold_dict)
    request.analyzer.parameters["window_size"] = "10"
    request.analyzer.parameters["window_slider"] = "5"
    request.analyzer.batch_min_duration_s = 10
    request.analyzer.batch_min_size = 5

    i_kpi_id = KpiId()
    i_kpi_id.kpi_id.uuid = kpi_input_uuid
    request.analyzer.input_kpi_ids.append(i_kpi_id)

    o_kpi_id = KpiId()
    o_kpi_id.kpi_id.uuid = kpi_output_uuid
    request.analyzer.output_kpi_ids.append(o_kpi_id)

    # Policy
    action = PolicyRuleAction()
    action.action = PolicyRuleActionEnum.POLICY_RULE_ACTION_CALL_SERVICE_RPC
    request.policy.policyRuleBasic.policyRuleId.uuid.uuid = str(uuid.uuid4())
    request.policy.policyRuleBasic.actionList.append(action)
    request.policy.policyRuleBasic.policyRuleState.policyRuleState = PolicyRuleStateEnum.POLICY_UNDEFINED
    request.policy.policyRuleBasic.policyRuleState.policyRuleStateMessage = "About to insert policy"
    rule_kpi = PolicyRuleKpiId()
    rule_kpi.policyRuleKpiUuid.uuid = o_kpi_id.kpi_id.uuid
    request.policy.policyRuleBasic.policyRuleKpiList.append(rule_kpi)
    request.policy.serviceId.context_id.context_uuid.uuid = context_uuid
    request.policy.serviceId.service_uuid.uuid = target_service_uuid

    return request
