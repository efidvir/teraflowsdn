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

from common.Constants import DEFAULT_CONTEXT_NAME
from common.proto.context_pb2 import ContextId
from common.tools.descriptor.Loader import DescriptorLoader, validate_empty_scenario
from common.tools.object_factory.Context import json_context_id

# pylint: disable=unused-import
from .conftest import (
    selected_tfs_client_bundle, selected_tfs_profile, selected_topology_descriptor
)
from .Helper import validate_descriptor_state

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

ADMIN_CONTEXT_ID = ContextId(**json_context_id(DEFAULT_CONTEXT_NAME))


def test_scenario_cleanup(
    selected_tfs_client_bundle,
    selected_tfs_profile: str,
    selected_topology_descriptor: str,
) -> None:
    context_client = selected_tfs_client_bundle.context
    device_client = selected_tfs_client_bundle.device

    response = context_client.GetContext(ADMIN_CONTEXT_ID)
    assert len(response.service_ids) == 0
    assert len(response.slice_ids) == 0

    descriptor_loader = DescriptorLoader(
        descriptors_file=selected_topology_descriptor,
        context_client=context_client,
        device_client=device_client,
    )
    validate_descriptor_state(context_client, descriptor_loader, selected_tfs_profile)
    descriptor_loader.unload()
    validate_empty_scenario(context_client)
