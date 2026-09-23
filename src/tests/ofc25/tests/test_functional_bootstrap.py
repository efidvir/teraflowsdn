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
import time

from common.Constants import DEFAULT_CONTEXT_NAME
from common.proto.context_pb2 import ContextId, DeviceOperationalStatusEnum, Empty
from common.tools.descriptor.Loader import DescriptorLoader, check_descriptor_load_results, validate_empty_scenario
from common.tools.grpc.Tools import grpc_message_list_to_json_string, grpc_message_to_json, grpc_message_to_json_string
from common.tools.object_factory.Context import json_context_id

# pylint: disable=unused-import
from .conftest import (
    selected_tfs_client_bundle, selected_tfs_profile, selected_topology_descriptor
)
from .Helper import split_imported_devices, validate_descriptor_state

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

ADMIN_CONTEXT_ID = ContextId(**json_context_id(DEFAULT_CONTEXT_NAME))


def _check_devices_enabled_or_raise(context_client, profile_name: str, max_retry: int = 10, wait_seconds: float = 1.0) -> None:
    op_status_enabled = DeviceOperationalStatusEnum.DEVICEOPERATIONALSTATUS_ENABLED

    num_devices = -1
    num_devices_enabled = 0
    num_retry = 0
    disabled_devices = list()

    while (num_retry < max_retry) and (num_devices != num_devices_enabled):
        time.sleep(wait_seconds)
        response = context_client.ListDevices(Empty())
        num_devices = len(response.devices)
        local_devices, imported_devices = split_imported_devices(response.devices)
        num_devices_enabled = 0
        disabled_devices = list()
        for device in response.devices:
            if device.device_operational_status == op_status_enabled:
                num_devices_enabled += 1
            else:
                disabled_devices.append(grpc_message_to_json(device))
        LOGGER.info(
            '[%s] Num Devices enabled: %d/%d (local=%d imported=%d)',
            profile_name,
            num_devices_enabled,
            num_devices,
            len(local_devices),
            len(imported_devices),
        )
        LOGGER.info('[%s] Local devices: %s', profile_name, grpc_message_list_to_json_string(local_devices))
        LOGGER.info('[%s] Imported devices: %s', profile_name, grpc_message_list_to_json_string(imported_devices))
        num_retry += 1

    if num_devices_enabled != num_devices:
        msg = '[{:s}] Devices enabled timeout after {:d} retries: {:d}/{:d}; disabled={:s}'
        raise Exception(msg.format(profile_name, max_retry, num_devices_enabled, num_devices, str(disabled_devices)))

    LOGGER.info('[%s] Devices: %s', profile_name, grpc_message_to_json_string(response))


def test_scenario_bootstrap(
    selected_tfs_client_bundle,
    selected_tfs_profile: str,
    selected_topology_descriptor: str,
) -> None:
    context_client = selected_tfs_client_bundle.context
    device_client = selected_tfs_client_bundle.device

    validate_empty_scenario(context_client)

    descriptor_loader = DescriptorLoader(
        descriptors_file=selected_topology_descriptor,
        context_client=context_client,
        device_client=device_client,
    )
    results = descriptor_loader.process()
    check_descriptor_load_results(results, descriptor_loader)
    validate_descriptor_state(context_client, descriptor_loader, selected_tfs_profile)

    response = context_client.GetContext(ADMIN_CONTEXT_ID)
    assert len(response.service_ids) == 0
    assert len(response.slice_ids) == 0


def test_scenario_devices_enabled(
    selected_tfs_client_bundle,
    selected_tfs_profile: str,
) -> None:
    context_client = selected_tfs_client_bundle.context
    _check_devices_enabled_or_raise(context_client, selected_tfs_profile)
