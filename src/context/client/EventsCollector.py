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
from common.proto.context_pb2 import Empty
from common.tools.grpc.BaseEventCollector import BaseEventCollector
from context.client.ContextClient import ContextClient

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

class EventsCollector(BaseEventCollector):
    def __init__(
        self, context_client          : ContextClient,
        log_events_received           : bool = False,
        activate_context_collector    : bool = True,
        activate_topology_collector   : bool = True,
        activate_device_collector     : bool = True,
        activate_link_collector       : bool = True,
        activate_service_collector    : bool = True,
        activate_slice_collector      : bool = True,
        activate_connection_collector : bool = True,
    ) -> None:
        super().__init__()

        if activate_context_collector:
            self.install_collector(context_client.GetContextEvents, Empty(), log_events_received)
        if activate_topology_collector:
            self.install_collector(context_client.GetTopologyEvents, Empty(), log_events_received)
        if activate_device_collector:
            self.install_collector(context_client.GetDeviceEvents, Empty(), log_events_received)
        if activate_link_collector:
            self.install_collector(context_client.GetLinkEvents, Empty(), log_events_received)
        if activate_service_collector:
            self.install_collector(context_client.GetServiceEvents, Empty(), log_events_received)
        if activate_slice_collector:
            self.install_collector(context_client.GetSliceEvents, Empty(), log_events_received)
        if activate_connection_collector:
            self.install_collector(context_client.GetConnectionEvents, Empty(), log_events_received)
