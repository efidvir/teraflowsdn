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

from common.proto.context_pb2 import (
    ServiceId, ServiceStatusEnum, ServiceTypeEnum,
)
from common.tools.grpc.Tools import grpc_message_to_json_string
from common.tools.object_factory.Service import json_service_id
from context.client.ContextClient import ContextClient
from service.client.ServiceClient import ServiceClient
from tests.tools.test_tools_p4 import *

from .Fixtures import (  # pylint: disable=unused-import
    context_client, service_client,
)

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

DEV_NB = 5
P4_DEV_NB = 1
UE_NB = 1

BASIC_UPF_RULES = 22
PER_UE_RULES = 4

def test_service_deletion_upf(
    context_client : ContextClient, # pylint: disable=redefined-outer-name
    service_client : ServiceClient  # pylint: disable=redefined-outer-name
) -> None:
    # Get the current number of devices
    response = context_client.ListDevices(ADMIN_CONTEXT_ID)
    LOGGER.warning('Devices[{:d}] = {:s}'.format(len(response.devices), grpc_message_to_json_string(response)))

    # Total devices
    dev_nb = len(response.devices)
    assert dev_nb == DEV_NB

    # P4 devices
    p4_dev_nb = identify_number_of_p4_devices(response.devices)
    assert p4_dev_nb == P4_DEV_NB

    # Get the current number of rules in the P4 devices
    p4_rules_before_deletion = get_number_of_rules(response.devices)

    # Get the current number of services
    response = context_client.ListServices(ADMIN_CONTEXT_ID)
    services_nb_before_deletion = len(response.services)
    assert verify_active_service_type(response.services, ServiceTypeEnum.SERVICETYPE_UPF)

    for service in response.services:
        # Ignore services of other types
        if service.service_type != ServiceTypeEnum.SERVICETYPE_UPF:
            continue

        service_id = service.service_id
        assert service_id

        service_uuid = service_id.service_uuid.uuid
        context_uuid = service_id.context_id.context_uuid.uuid
        assert service.service_status.service_status == ServiceStatusEnum.SERVICESTATUS_ACTIVE

        # Delete L2 service
        service_client.DeleteService(ServiceId(**json_service_id(service_uuid, json_context_id(context_uuid))))

    # Get an updated view of the services
    response = context_client.ListServices(ADMIN_CONTEXT_ID)
    services_nb_after_deletion = len(response.services)
    assert services_nb_after_deletion == services_nb_before_deletion - 1, "Exactly one service must be deleted"

    # Get an updated view of the devices
    response = context_client.ListDevices(ADMIN_CONTEXT_ID)
    p4_rules_after_deletion = get_number_of_rules(response.devices)

    rules_diff = p4_rules_before_deletion - p4_rules_after_deletion

    desired_rules = (P4_DEV_NB * BASIC_UPF_RULES) + (UE_NB * PER_UE_RULES)

    assert p4_rules_after_deletion < p4_rules_before_deletion, "UPF service must contain some rules"
    assert rules_diff == desired_rules, \
        "UPF service must contain {} rules per device".format(desired_rules)
