# Copyright 2022-2026 ETSI SDG TeraFlowSDN (TFS) (https://tfs.etsi.org/)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import grpc, logging
from uuid import uuid4
from common.proto.analytics_frontend_pb2 import AnalyzerId
from common.proto.policy_pb2 import PolicyRuleState
from common.proto.automation_pb2 import ZSMCreateRequest, ZSMService

from analytics.frontend.client.AnalyticsFrontendClient import AnalyticsFrontendClient
from automation.client.PolicyClient import PolicyClient
from context.client.ContextClient import ContextClient
from automation.service.zsm_handler_api._ZSMHandler import _ZSMHandler


LOGGER = logging.getLogger(__name__)

class P4INTZSMPlugin(_ZSMHandler):
    def __init__(self):
        LOGGER.info('Init P4INTZSMPlugin')

    def zsmCreate(self, request : ZSMCreateRequest, context : grpc.ServicerContext): # type: ignore
        context_client = ContextClient()
        policy_client = PolicyClient()
        analytics_frontend_client = AnalyticsFrontendClient()

        # Verify the input target service ID
        try:
            target_service_id = context_client.GetService(request.target_service_id)
        except grpc.RpcError as ex:
            LOGGER.exception(f'Unable to get target service:\n{str(target_service_id)}')
            if ex.code() != grpc.StatusCode.NOT_FOUND: raise  # pylint: disable=no-member
            context_client.close()
            return self._zsm_create_response_empty()

        # Verify the input telemetry service ID
        try:
            telemetry_service_id = context_client.GetService(request.telemetry_service_id)
        except grpc.RpcError as ex:
            LOGGER.exception(f'Unable to get telemetry service:\n{str(telemetry_service_id)}')
            if ex.code() != grpc.StatusCode.NOT_FOUND: raise  # pylint: disable=no-member
            context_client.close()
            return self._zsm_create_response_empty()

        # Start an analyzer
        try:
            analyzer_id: AnalyzerId = analytics_frontend_client.StartAnalyzer(request.analyzer) # type: ignore
            LOGGER.info('Analyzer_id:\n{:s}'.format(str(analyzer_id)))
        except grpc.RpcError as ex:
            LOGGER.exception(f'Unable to start Analyzer:\n{str(request.analyzer)}')
            if ex.code() != grpc.StatusCode.NOT_FOUND: raise  # pylint: disable=no-member
            context_client.close()
            analytics_frontend_client.close()
            return self._zsm_create_response_empty()

        # Create a policy
        try:
            LOGGER.info(f'Policy:\n{str(request.policy)}')
            policy_rule_state: PolicyRuleState = policy_client.PolicyAddService(request.policy) # type: ignore
            LOGGER.info(f'Policy rule state:\n{policy_rule_state}')
        except Exception as ex:
            LOGGER.exception(f'Unable to create policy:\n{str(request.policy)}')
            LOGGER.exception(ex.code())
            # ToDo: Investigate why PolicyAddService throws exception
            # if ex.code() != grpc.StatusCode.NOT_FOUND: raise  # pylint: disable=no-member
            context_client.close()
            policy_client.close()
            return self._zsm_create_response_empty()

        context_client.close()
        analytics_frontend_client.close()
        policy_client.close()
        return self._zsm_create_response(request)

    def zsmDelete(self):
        LOGGER.info('zsmDelete method')

    def zsmGetById(self):
        LOGGER.info('zsmGetById method')

    def zsmGetByService(self):
        LOGGER.info('zsmGetByService method')

    def _zsm_create_response(self, request):
        response = ZSMService()
        automation_id = str(uuid4())
        response.zsmServiceId.uuid.uuid = automation_id
        response.serviceId.service_uuid.uuid = request.target_service_id.service_uuid.uuid
        return response

    def _zsm_create_response_empty(self):
        return ZSMService()