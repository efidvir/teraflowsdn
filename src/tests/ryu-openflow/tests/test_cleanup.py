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

import graphlib, logging, os
from typing import Dict, List, Tuple

from common.Constants import DEFAULT_CONTEXT_NAME
from common.proto.context_pb2 import ContextId, DeviceId, Empty
from common.tools.descriptor.Loader import validate_empty_scenario
from common.tools.grpc.Tools import grpc_message_to_json_string
from common.tools.object_factory.Context import json_context_id
from context.client.ContextClient import ContextClient
from device.client.DeviceClient import DeviceClient

from .Fixtures import (
    context_client, device_client,
)  # pylint: disable=unused-import

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

DESCRIPTOR_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'tfs-topology.json')
ADMIN_CONTEXT_ID = ContextId(**json_context_id(DEFAULT_CONTEXT_NAME))

def test_scenario_cleanup(
    context_client : ContextClient, # pylint: disable=redefined-outer-name
    device_client : DeviceClient,   # pylint: disable=redefined-outer-name
) -> None:
    # Verify the scenario has no services/slices
    response = context_client.GetContext(ADMIN_CONTEXT_ID)
    assert len(response.service_ids) == 0
    assert len(response.slice_ids) == 0

    # Automatic scenario cleanup does not work due to addition of virtual devices.
    # Doing it manually...

    link_ids = context_client.ListLinkIds(Empty())
    LOGGER.info('Link Ids: {:s}'.format(grpc_message_to_json_string(link_ids)))
    for link_id in link_ids.link_ids:
        context_client.RemoveLink(link_id)

    devices = context_client.ListDevices(Empty())
    LOGGER.info('Devices: {:s}'.format(grpc_message_to_json_string(devices)))

    dag_device_uuids = graphlib.TopologicalSorter()
    device_uuid_to_data : Dict[str, Tuple[DeviceId, str]] = dict()

    for device in devices.devices:
        device_id = device.device_id
        device_uuid = device_id.device_uuid.uuid
        dag_device_uuids.add(device_uuid)

        device_uuid_to_data[device_uuid] = (device_id, device.name)

        controller_uuid = device.controller_id.device_uuid.uuid
        if len(controller_uuid) == 0: continue
        dag_device_uuids.add(controller_uuid, device_uuid)

    sorted_device_uuids = list(dag_device_uuids.static_order())

    LOGGER.info('device_uuid_to_data: {:s}'.format(str(device_uuid_to_data)))
    LOGGER.info('sorted_device_uuids: {:s}'.format(str(sorted_device_uuids)))
           
    for device_uuid in sorted_device_uuids:
        device_id = device_uuid_to_data[device_uuid][0]
        context_client.RemoveDevice(device_id)

    context_ids = context_client.ListContextIds(Empty())
    LOGGER.info('Context Ids: {:s}'.format(grpc_message_to_json_string(context_ids)))
    for context_id in context_ids.context_ids:
        topology_ids = context_client.ListTopologyIds(context_id)
        LOGGER.info('Topology Ids: {:s}'.format(grpc_message_to_json_string(topology_ids)))
        for topology_id in topology_ids.topology_ids:
            context_client.RemoveTopology(topology_id)
        context_client.RemoveContext(context_id)

    response = context_client.ListLinks(Empty())
    LOGGER.info('Links: {:s}'.format(grpc_message_to_json_string(response)))

    response = context_client.ListDevices(Empty())
    LOGGER.info('Devices: {:s}'.format(grpc_message_to_json_string(response)))

    response = context_client.ListContexts(Empty())
    LOGGER.info('Contexts: {:s}'.format(grpc_message_to_json_string(response)))

    validate_empty_scenario(context_client)
