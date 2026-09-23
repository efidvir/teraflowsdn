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

from common.tools.descriptor.Loader import DescriptorLoader

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


def test_delete_virtual_links(
    tfs_clients,
) -> None:
    ip_context_client = tfs_clients[PROFILE_IP].context
    ip_device_client = tfs_clients[PROFILE_IP].device
    ip_vnt_manager_client = tfs_clients[PROFILE_IP].vnt_manager
    e2e_context_client = tfs_clients[PROFILE_E2E].context
    opt_context_client = tfs_clients[PROFILE_OPT].context

    assert ip_vnt_manager_client is not None

    expected_virtual_link_names = {link_name for _, link_name in VIRTUAL_LINK_DESCRIPTORS}
    wait_for_state_or_raise(
        ip_context_client=ip_context_client,
        e2e_context_client=e2e_context_client,
        opt_context_client=opt_context_client,
        expected_virtual_link_uuids=None,
        expected_virtual_link_names=expected_virtual_link_names,
        expected_e2e_services=len(VIRTUAL_LINK_DESCRIPTORS),
        expected_opt_services=len(VIRTUAL_LINK_DESCRIPTORS),
        expected_opt_connections=build_expected_optical_connections(expected_virtual_link_names),
    )

    for remaining, (descriptor_name, virtual_link_name) in zip(
        [2, 1, 0], reversed(VIRTUAL_LINK_DESCRIPTORS)
    ):
        descriptor_file = os.path.join(DESCRIPTORS_DIR, descriptor_name)
        LOGGER.info(
            'Deleting virtual link from descriptor %s; expecting %d remaining E2E services afterwards',
            descriptor_file, remaining
        )
        descriptor_loader = DescriptorLoader(
            descriptors_file=descriptor_file,
            context_client=ip_context_client,
            device_client=ip_device_client,
            vntm_client=ip_vnt_manager_client,
        )
        descriptor_loader.unload()
        LOGGER.info('Virtual link removal submitted successfully for %s', virtual_link_name)

        expected_virtual_link_names.remove(virtual_link_name)
        LOGGER.info(
            'Waiting for propagated state after deleting %s: expected_virtual_link_names=%s '
            'expected_e2e_services=%d',
            virtual_link_name, str(sorted(expected_virtual_link_names)), remaining
        )
        wait_for_state_or_raise(
            ip_context_client=ip_context_client,
            e2e_context_client=e2e_context_client,
            opt_context_client=opt_context_client,
            expected_virtual_link_uuids=None,
            expected_virtual_link_names=expected_virtual_link_names,
            expected_e2e_services=remaining,
            expected_opt_services=remaining,
            expected_opt_connections=build_expected_optical_connections(expected_virtual_link_names),
        )
