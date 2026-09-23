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
from typing import Set

from common.tools.descriptor.Loader import DescriptorLoader, check_descriptor_load_results

# pylint: disable=unused-import
from .Fixtures import PROFILE_E2E, PROFILE_IP, PROFILE_OPT, tfs_clients
from .Helper import (
    DESCRIPTORS_DIR,
    VIRTUAL_LINK_DESCRIPTORS,
    build_expected_optical_connections,
    wait_for_state_or_raise,
)

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

def test_create_virtual_link(
    tfs_clients,
) -> None:
    ip_context_client = tfs_clients[PROFILE_IP].context
    ip_device_client = tfs_clients[PROFILE_IP].device
    ip_vnt_manager_client = tfs_clients[PROFILE_IP].vnt_manager
    e2e_context_client = tfs_clients[PROFILE_E2E].context
    opt_context_client = tfs_clients[PROFILE_OPT].context

    assert ip_vnt_manager_client is not None

    # Initial state: no services in any TFS and no virtual links in IP.
    wait_for_state_or_raise(
        ip_context_client=ip_context_client,
        e2e_context_client=e2e_context_client,
        opt_context_client=opt_context_client,
        expected_virtual_link_uuids=None,
        expected_virtual_link_names=set(),
        expected_e2e_services=0,
        expected_opt_services=0,
        expected_opt_connections={},
    )

    expected_virtual_link_names: Set[str] = set()
    for index, (descriptor_name, virtual_link_name) in enumerate(VIRTUAL_LINK_DESCRIPTORS, start=1):
        descriptor_file = os.path.join(DESCRIPTORS_DIR, descriptor_name)
        LOGGER.info(
            'Creating virtual link step %d/%d from descriptor %s',
            index, len(VIRTUAL_LINK_DESCRIPTORS), descriptor_file
        )
        descriptor_loader = DescriptorLoader(
            descriptors_file=descriptor_file,
            context_client=ip_context_client,
            device_client=ip_device_client,
            vntm_client=ip_vnt_manager_client,
        )
        results = descriptor_loader.process()
        check_descriptor_load_results(results, descriptor_loader)
        LOGGER.info('Virtual link request submitted successfully for %s', virtual_link_name)

        expected_virtual_link_names.add(virtual_link_name)
        LOGGER.info(
            'Waiting for propagated state after creating %s: expected_virtual_link_names=%s '
            'expected_e2e_services=%d',
            virtual_link_name, str(sorted(expected_virtual_link_names)), index
        )
        expected_opt_connections = build_expected_optical_connections(expected_virtual_link_names)
        wait_for_state_or_raise(
            ip_context_client=ip_context_client,
            e2e_context_client=e2e_context_client,
            opt_context_client=opt_context_client,
            expected_virtual_link_uuids=None,
            expected_virtual_link_names=expected_virtual_link_names,
            expected_e2e_services=index,
            expected_opt_services=index,
            expected_opt_connections=expected_opt_connections,
        )
