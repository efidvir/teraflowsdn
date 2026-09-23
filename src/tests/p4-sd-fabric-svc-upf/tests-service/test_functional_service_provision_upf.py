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
import os

from common.proto.context_pb2 import ServiceTypeEnum
from common.tools.descriptor.Loader import (
    DescriptorLoader, check_descriptor_load_results,
)
from common.tools.grpc.Tools import grpc_message_to_json_string
from context.client.ContextClient import ContextClient
from device.client.DeviceClient import DeviceClient
from service.client.ServiceClient import ServiceClient
from tests.tools.test_tools_p4 import *

from .Fixtures import (  # pylint: disable=unused-import
    context_client, device_client, service_client,
)

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

DEV_NB = 5
P4_DEV_NB = 1
UE_NB = 1

BASIC_UPF_RULES = 22
PER_UE_RULES = 4

TEST_PATH = os.path.join(
    os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)
    )) + '/descriptors')
assert os.path.exists(TEST_PATH), "Invalid path to tests"

DESC_FILE_SERVICE_P4_UPF = os.path.join(TEST_PATH, 'service-upf-ui.json')
assert os.path.exists(DESC_FILE_SERVICE_P4_UPF),\
    "Invalid path to the UPF service descriptor"

def test_service_creation_upf(
    context_client : ContextClient, # pylint: disable=redefined-outer-name
    device_client  : DeviceClient,  # pylint: disable=redefined-outer-name
    service_client : ServiceClient  # pylint: disable=redefined-outer-name
) -> None:
    # Get the current number of services
    response = context_client.ListServices(ADMIN_CONTEXT_ID)
    services_nb_before = len(response.services)

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
    p4_rules_before = get_number_of_rules(response.devices)

    # Load service
    descriptor_loader = DescriptorLoader(
        descriptors_file=DESC_FILE_SERVICE_P4_UPF,
        context_client=context_client, device_client=device_client, service_client=service_client
    )
    results = descriptor_loader.process()
    check_descriptor_load_results(results, descriptor_loader)

    # Get an updated view of the services
    response = context_client.ListServices(ADMIN_CONTEXT_ID)
    services_nb_after = len(response.services)
    assert services_nb_after == services_nb_before + 1, "Exactly one service must be in place"
    assert verify_active_service_type(response.services, ServiceTypeEnum.SERVICETYPE_UPF)

    # Get an updated view of the devices
    response = context_client.ListDevices(ADMIN_CONTEXT_ID)
    p4_rules_after = get_number_of_rules(response.devices)

    rules_diff = p4_rules_after - p4_rules_before

    desired_rules = (P4_DEV_NB * BASIC_UPF_RULES) + (UE_NB * PER_UE_RULES)

    assert p4_rules_after > p4_rules_before, "UPF service must install some rules"
    assert rules_diff == desired_rules, \
        "UPF service must install {} rules per device".format(desired_rules)
