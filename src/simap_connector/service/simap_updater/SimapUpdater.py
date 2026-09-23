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


import logging, queue, threading, uuid
from typing import Any, List, Optional, Set, Tuple
from common.Constants import DEFAULT_TOPOLOGY_NAME
from common.DeviceTypes import DeviceTypeEnum
from common.proto.context_pb2 import (
    ContextEvent, DeviceEvent, Empty, LinkEvent, ServiceEvent, ServiceStatusEnum,
    SliceEvent, TopologyEvent, ConnectionEvent
)
from common.tools.grpc.BaseEventCollector  import BaseEventCollector
from common.tools.grpc.BaseEventDispatcher import BaseEventDispatcher
from common.tools.grpc.Tools      import grpc_message_to_json_string, grpc_message_to_json
from context.client.ContextClient import ContextClient
from simap_connector.service.telemetry.worker.data.Resources import (
    ResourceLink, Resources, SyntheticSampler
)
from simap_connector.service.telemetry.worker._Worker import WorkerTypeEnum
from simap_connector.service.telemetry.TelemetryPool  import SynthesizerWorker, TelemetryPool
from .RealSimaps   import set_simap_network, delete_simap_network
from .AllowedLinks import ALLOWED_LINKS_PER_CONTROLLER, LINKS_CAPACITY
# from .MockSimaps import delete_mock_simap, set_mock_simap
from .ObjectCache  import CachedEntities, ObjectCache
from .SimapClient  import SimapClient
from .Tools        import get_device_endpoint, get_link_endpoint, get_connection_endpoints_and_links #, get_service_endpoint

LOGGER = logging.getLogger(__name__)


SKIPPED_DEVICE_TYPES = {
    DeviceTypeEnum.EMULATED_IP_SDN_CONTROLLER.value,
    DeviceTypeEnum.IP_SDN_CONTROLLER.value,
    DeviceTypeEnum.NCE.value,
    DeviceTypeEnum.TERAFLOWSDN_CONTROLLER.value,
}


class EventDispatcher(BaseEventDispatcher):
    def __init__(
        self, events_queue : queue.PriorityQueue,
        simap_client       : SimapClient,
        context_client     : ContextClient,
        telemetry_pool     : TelemetryPool,
        terminate          : Optional[threading.Event] = None
    ) -> None:
        super().__init__(events_queue, terminate)
        self._simap_client    = simap_client
        self._context_client  = context_client
        self._telemetry_pool  = telemetry_pool
        self._object_cache    = ObjectCache(self._context_client)
        self._skipped_devices : Set[str] = set()


    def _add_skipped_device(self, device) -> None:
        self._skipped_devices.add(device.device_id.device_uuid.uuid)
        self._skipped_devices.add(device.name)


    def _remove_skipped_device(self, device) -> None:
        self._skipped_devices.discard(device.device_id.device_uuid.uuid)
        self._skipped_devices.discard(device.name)


    def dispatch(self, event : Any) -> None:
        MSG = 'Unexpected Event: {:s}'
        LOGGER.warning(MSG.format(grpc_message_to_json_string(event)))


    def dispatch_context(self, context_event : ContextEvent) -> None:
        MSG = 'Skipping Context Event: {:s}'
        LOGGER.debug(MSG.format(grpc_message_to_json_string(context_event)))


    def dispatch_slice(self, slice_event : SliceEvent) -> None:
        MSG = 'Skipping Slice Event: {:s}'
        LOGGER.debug(MSG.format(grpc_message_to_json_string(slice_event)))

#  ----- Topology Events -----

    def _dispatch_topology_set(self, topology_event : TopologyEvent) -> bool:
        MSG = 'Processing Topology Event: {:s}'
        LOGGER.info(MSG.format(grpc_message_to_json_string(topology_event)))

        topology_uuid = topology_event.topology_id.topology_uuid.uuid
        topology = self._object_cache.get(CachedEntities.TOPOLOGY, topology_uuid)
        topology_name = topology.name

        supporting_network_ids = list()
        if topology_name != DEFAULT_TOPOLOGY_NAME:
            supporting_network_ids.append(DEFAULT_TOPOLOGY_NAME)

        # Theoretically it should be create(), but given we have multiple clients
        # updating same SIMAP server, use update to skip tricks on get-check-create-or-update.
        self._simap_client.network(topology_name).update(
            supporting_network_ids=supporting_network_ids
        )
        return True


    def dispatch_topology_create(self, topology_event : TopologyEvent) -> None:
        if not self._dispatch_topology_set(topology_event): return

        MSG = 'Topology Create: {:s}'
        LOGGER.info(MSG.format(grpc_message_to_json_string(topology_event)))


    def dispatch_topology_update(self, topology_event : TopologyEvent) -> None:
        if not self._dispatch_topology_set(topology_event): return

        MSG = 'Topology Updated: {:s}'
        LOGGER.info(MSG.format(grpc_message_to_json_string(topology_event)))


    def dispatch_topology_remove(self, topology_event : TopologyEvent) -> None:
        MSG = 'Processing Topology Event: {:s}'
        LOGGER.info(MSG.format(grpc_message_to_json_string(topology_event)))

        topology_uuid = topology_event.topology_id.topology_uuid.uuid
        topology = self._object_cache.get(CachedEntities.TOPOLOGY, topology_uuid)
        topology_name = topology.name
        self._simap_client.network(topology_name).delete()

        self._object_cache.delete(CachedEntities.TOPOLOGY, topology_uuid)
        self._object_cache.delete(CachedEntities.TOPOLOGY, topology_name)

        MSG = 'Topology Remove: {:s}'
        LOGGER.info(MSG.format(grpc_message_to_json_string(topology_event)))

#  ----- Device Events -----

    def _dispatch_device_set(self, device_event : DeviceEvent) -> bool:
        MSG = 'Processing Device Event: {:s}'
        LOGGER.info(MSG.format(grpc_message_to_json_string(device_event)))

        device_uuid = device_event.device_id.device_uuid.uuid
        device = self._object_cache.get(CachedEntities.DEVICE, device_uuid, force_update=True)

        device_type = device.device_type
        if device_type in SKIPPED_DEVICE_TYPES:
            self._add_skipped_device(device)
            MSG = (
                'DeviceEvent({:s}) skipped, is of a skipped device type. '
                'SIMAP should be updated by him: {:s}'
            )
            str_device_event = grpc_message_to_json_string(device_event)
            str_device = grpc_message_to_json_string(device)
            LOGGER.warning(MSG.format(str_device_event, str_device))
            return False

        #device_controller_uuid = device.controller_id.device_uuid.uuid
        #if len(device_controller_uuid) > 0:
        #    self._add_skipped_device(device)
        #    MSG = (
        #        'DeviceEvent({:s}) skipped, is a remotely-managed device. '
        #        'SIMAP should be populated by remote controller: {:s}'
        #    )
        #    str_device_event = grpc_message_to_json_string(device_event)
        #    str_device = grpc_message_to_json_string(device)
        #    LOGGER.warning(MSG.format(str_device_event, str_device))
        #    return

        topology_uuid, endpoint_names = get_device_endpoint(device)
        if topology_uuid is None:
            #self._add_skipped_device(device)
            MSG = 'DeviceEvent({:s}) skipped, no endpoints to identify topology: {:s}'
            str_device_event = grpc_message_to_json_string(device_event)
            str_device = grpc_message_to_json_string(device)
            LOGGER.warning(MSG.format(str_device_event, str_device))
            return False

        topology = self._object_cache.get(CachedEntities.TOPOLOGY, topology_uuid)
        topology_name = topology.name

        te_topo = self._simap_client.network(topology_name)
        te_topo.update()

        device_name = device.name
        te_device = te_topo.node(device_name)
        te_device.update()

        for endpoint_name in endpoint_names:
            te_device.termination_point(endpoint_name).update()

        #self._remove_skipped_device(device)
        return True


    def dispatch_device_create(self, device_event : DeviceEvent) -> None:
        if not self._dispatch_device_set(device_event): return

        MSG = 'Device Created: {:s}'
        LOGGER.info(MSG.format(grpc_message_to_json_string(device_event)))


    def dispatch_device_update(self, device_event : DeviceEvent) -> None:
        if not self._dispatch_device_set(device_event): return

        MSG = 'Device Updated: {:s}'
        LOGGER.info(MSG.format(grpc_message_to_json_string(device_event)))


    def dispatch_device_remove(self, device_event : DeviceEvent) -> None:
        MSG = 'Processing Device Event: {:s}'
        LOGGER.info(MSG.format(grpc_message_to_json_string(device_event)))

        device_uuid = device_event.device_id.device_uuid.uuid
        device = self._object_cache.get(CachedEntities.DEVICE, device_uuid)

        device_type = device.device_type
        if device_type in SKIPPED_DEVICE_TYPES:
            self._add_skipped_device(device)
            MSG = (
                'DeviceEvent({:s}) skipped, is of a skipped device type. '
                'SIMAP should be updated by him: {:s}'
            )
            str_device_event = grpc_message_to_json_string(device_event)
            str_device = grpc_message_to_json_string(device)
            LOGGER.warning(MSG.format(str_device_event, str_device))
            return

        device_controller_uuid = device.controller_id.device_uuid.uuid
        if len(device_controller_uuid) > 0:
            # if it is a delete of a remotely-managed device,
            # should be managed by owner controller
            #self._add_skipped_device(device)
            MSG = (
                'DeviceEvent({:s}) skipped, is a remotely-managed device. '
                'SIMAP should be updated by remote controller: {:s}'
            )
            str_device_event = grpc_message_to_json_string(device_event)
            str_device = grpc_message_to_json_string(device)
            LOGGER.warning(MSG.format(str_device_event, str_device))
            return

        topology_uuid, endpoint_names = get_device_endpoint(device)
        topology = self._object_cache.get(CachedEntities.TOPOLOGY, topology_uuid)
        topology_name = topology.name

        te_topo = self._simap_client.network(topology_name)
        te_topo.update()

        device_name = device.name
        te_device = te_topo.node(device_name)
        for endpoint_name in endpoint_names:
            te_device.termination_point(endpoint_name).delete()

            endpoint = self._object_cache.get(CachedEntities.ENDPOINT, device_uuid, endpoint_name)
            endpoint_uuid = endpoint.endpoint_id.endpoint_uuid.uuid
            self._object_cache.delete(CachedEntities.DEVICE, device_uuid, endpoint_uuid)
            self._object_cache.delete(CachedEntities.DEVICE, device_uuid, endpoint_name)
            self._object_cache.delete(CachedEntities.DEVICE, device_name, endpoint_uuid)
            self._object_cache.delete(CachedEntities.DEVICE, device_name, endpoint_name)

        te_device.delete()

        self._remove_skipped_device(device)
        self._object_cache.delete(CachedEntities.DEVICE, device_uuid)
        self._object_cache.delete(CachedEntities.DEVICE, device_name)

        MSG = 'Device Remove: {:s}'
        LOGGER.info(MSG.format(grpc_message_to_json_string(device_event)))

# ----- Link Events -----

    def _dispatch_link_set(self, link_event : LinkEvent) -> bool:
        MSG = 'Processing Link Event: {:s}'
        LOGGER.info(MSG.format(grpc_message_to_json_string(link_event)))

        link_uuid = link_event.link_id.link_uuid.uuid
        link = self._object_cache.get(CachedEntities.LINK, link_uuid)
        link_name = link.name

        topology_uuid, endpoint_uuids = get_link_endpoint(link)
        if topology_uuid is None:
            MSG = 'LinkEvent({:s}) skipped, no endpoint_ids to identify topology: {:s}'
            str_link_event = grpc_message_to_json_string(link_event)
            str_link = grpc_message_to_json_string(link)
            LOGGER.warning(MSG.format(str_link_event, str_link))
            return False

        topology = self._object_cache.get(CachedEntities.TOPOLOGY, topology_uuid)
        topology_name = topology.name

        te_topo = self._simap_client.network(topology_name)
        te_topo.update()

        topologies = self._object_cache.get_all(CachedEntities.TOPOLOGY, fresh=False)
        topology_names = {t.name for t in topologies}
        topology_names.discard(DEFAULT_TOPOLOGY_NAME)
        if len(topology_names) != 1:
            MSG = 'LinkEvent({:s}) skipped, unable to identify self-controller'
            str_link_event = grpc_message_to_json_string(link_event)
            LOGGER.warning(MSG.format(str_link_event))
            return False
        domain_name = topology_names.pop()  # trans-pkt/agg/e2e

        allowed_link_names = ALLOWED_LINKS_PER_CONTROLLER.get(domain_name, set())
        if link_name not in allowed_link_names: return False

        src_device   = self._object_cache.get(CachedEntities.DEVICE,   endpoint_uuids[0][0], force_update =True )
        src_endpoint = self._object_cache.get(CachedEntities.ENDPOINT, *(endpoint_uuids[0]), auto_retrieve=False)
        dst_device   = self._object_cache.get(CachedEntities.DEVICE,   endpoint_uuids[1][0], force_update =True )
        dst_endpoint = self._object_cache.get(CachedEntities.ENDPOINT, *(endpoint_uuids[1]), auto_retrieve=False)

        # Skip links that connect two management endpoints
        if src_endpoint is not None and dst_endpoint is not None:
            if str(src_endpoint.name).lower() == 'mgmt' and str(dst_endpoint.name).lower() == 'mgmt':
                MSG = 'LinkEvent({:s}) skipped, connects two management endpoints: {:s}'
                str_link_event = grpc_message_to_json_string(link_event)
                str_link = grpc_message_to_json_string(link)
                LOGGER.warning(MSG.format(str_link_event, str_link))
                return False

        # Skip links that connect to devices previously marked as skipped
        src_uuid = src_device.device_id.device_uuid.uuid
        dst_uuid = dst_device.device_id.device_uuid.uuid
        src_name = src_device.name
        dst_name = dst_device.name
        if (src_uuid in self._skipped_devices or src_name in self._skipped_devices
            or dst_uuid in self._skipped_devices or dst_name in self._skipped_devices):
            MSG = 'LinkEvent({:s}) skipped, connects to skipped device(s): {:s}'
            str_link_event = grpc_message_to_json_string(link_event)
            str_link = grpc_message_to_json_string(link)
            LOGGER.warning(MSG.format(str_link_event, str_link))
            return False

        try:
            if src_device is None:
                MSG = 'Device({:s}) not found in cache'
                raise Exception(MSG.format(str(endpoint_uuids[0][0])))
            if src_endpoint is None:
                MSG = 'Endpoint({:s}) not found in cache'
                raise Exception(MSG.format(str(endpoint_uuids[0])))
            if dst_device is None:
                MSG = 'Device({:s}) not found in cache'
                raise Exception(MSG.format(str(endpoint_uuids[1][0])))
            if dst_endpoint is None:
                MSG = 'Endpoint({:s}) not found in cache'
                raise Exception(MSG.format(str(endpoint_uuids[1])))
        except Exception as e:
            MSG = '{:s} in Link({:s})'
            raise Exception(MSG.format(str(e), grpc_message_to_json_string(link))) from e

        te_link = te_topo.link(link_name)
        te_link.update(src_device.name, src_endpoint.name, dst_device.name, dst_endpoint.name)

        # worker_name = '{:s}:{:s}'.format(topology_name, link_name)
        # resources   = Resources()
        # resources.links.append(ResourceLink(
        #     domain_name = topology_name, 
        #     link_name   = link_name,
        #     metrics_sampler = SyntheticSampler.create_random(
        #         connection_count = 0,
        #         link_capacity    = LINKS_CAPACITY.get(link_name, 100.0)
        #     ),
        #     related_service_ids=[],
        # ))
        # sampling_interval = 1.0
        # self._telemetry_pool.start_synthesizer(worker_name, resources, sampling_interval)

        return True


    def dispatch_link_create(self, link_event : LinkEvent) -> None:
        if not self._dispatch_link_set(link_event): return

        MSG = 'Link Created: {:s}'
        LOGGER.info(MSG.format(grpc_message_to_json_string(link_event)))


    def dispatch_link_update(self, link_event : LinkEvent) -> None:
        if not self._dispatch_link_set(link_event): return

        MSG = 'Link Updated: {:s}'
        LOGGER.info(MSG.format(grpc_message_to_json_string(link_event)))


    def dispatch_link_remove(self, link_event : LinkEvent) -> None:
        MSG = 'Processing Link Event: {:s}'
        LOGGER.info(MSG.format(grpc_message_to_json_string(link_event)))

        link_uuid = link_event.link_id.link_uuid.uuid
        link = self._object_cache.get(CachedEntities.LINK, link_uuid)
        link_name = link.name

        topology_uuid, endpoint_uuids = get_link_endpoint(link)
        topology = self._object_cache.get(CachedEntities.TOPOLOGY, topology_uuid)
        topology_name = topology.name

        te_topo = self._simap_client.network(topology_name)
        te_topo.update()

        src_device   = self._object_cache.get(CachedEntities.DEVICE,   endpoint_uuids[0][0], force_update =True )
        src_endpoint = self._object_cache.get(CachedEntities.ENDPOINT, *(endpoint_uuids[0]), auto_retrieve=False)
        dst_device   = self._object_cache.get(CachedEntities.DEVICE,   endpoint_uuids[1][0], force_update =True )
        dst_endpoint = self._object_cache.get(CachedEntities.ENDPOINT, *(endpoint_uuids[1]), auto_retrieve=False)

        # Skip links that connect two management endpoints
        if src_endpoint is not None and dst_endpoint is not None:
            if str(src_endpoint.name).lower() == 'mgmt' and str(dst_endpoint.name).lower() == 'mgmt':
                MSG = 'LinkEvent({:s}) skipped, connects two management endpoints: {:s}'
                str_link_event = grpc_message_to_json_string(link_event)
                str_link = grpc_message_to_json_string(link)
                LOGGER.warning(MSG.format(str_link_event, str_link))
                return

        # Skip links that connect to devices previously marked as skipped
        src_uuid = src_device.device_id.device_uuid.uuid
        dst_uuid = dst_device.device_id.device_uuid.uuid
        src_name = src_device.name
        dst_name = dst_device.name
        if (src_uuid in self._skipped_devices or src_name in self._skipped_devices
            or dst_uuid in self._skipped_devices or dst_name in self._skipped_devices):
            MSG = 'LinkEvent({:s}) skipped, connects to skipped device(s): {:s}'
            str_link_event = grpc_message_to_json_string(link_event)
            str_link = grpc_message_to_json_string(link)
            LOGGER.warning(MSG.format(str_link_event, str_link))
            return

        te_link = te_topo.link(link_name)
        te_link.delete()

        self._object_cache.delete(CachedEntities.LINK, link_uuid)
        self._object_cache.delete(CachedEntities.LINK, link_name)

        # worker_name = '{:s}:{:s}'.format(topology_name, link_name)
        # self._telemetry_pool.stop_worker(WorkerTypeEnum.SYNTHESIZER, worker_name)

        MSG = 'Link Removed: {:s}'
        LOGGER.info(MSG.format(grpc_message_to_json_string(link_event)))

#  ----- Service Events -----

    def _dispatch_service_set(self, service_event : ServiceEvent) -> bool:
        MSG = 'Processing Service Event: {:s}'
        LOGGER.info(MSG.format(grpc_message_to_json_string(service_event)))

        service_uuid = service_event.service_id.service_uuid.uuid
        service = self._object_cache.get(CachedEntities.SERVICE, service_uuid)
        service_name = service.name

        try:
            uuid.UUID(hex=service_name)
            # skip it if properly parsed, means it is a service with a UUID-based name, i.e., a sub-service
            MSG = 'ServiceEvent({:s}) skipped, it is a subservice: {:s}'
            str_service_event = grpc_message_to_json_string(service_event)
            str_service = grpc_message_to_json_string(service)
            LOGGER.warning(MSG.format(str_service_event, str_service))
            return False
        except: # pylint: disable=bare-except
            pass

        #topology_uuid, endpoint_uuids = get_service_endpoint(service)

        #if topology_uuid is None:
        #    MSG = 'ServiceEvent({:s}) skipped, no endpoint_ids to identify topology: {:s}'
        #    str_service_event = grpc_message_to_json_string(service_event)
        #    str_service = grpc_message_to_json_string(service)
        #    LOGGER.warning(MSG.format(str_service_event, str_service))
        #    return False

        #if len(endpoint_uuids) < 2:
        #    MSG = 'ServiceEvent({:s}) skipped, not enough endpoint_ids to compose link: {:s}'
        #    str_service_event = grpc_message_to_json_string(service_event)
        #    str_service = grpc_message_to_json_string(service)
        #    LOGGER.warning(MSG.format(str_service_event, str_service))
        #    return False

        # topologies = self._object_cache.get_all(CachedEntities.TOPOLOGY, fresh=False)
        # topology_names = {t.name for t in topologies}
        # topology_names.discard(DEFAULT_TOPOLOGY_NAME)
        # if len(topology_names) != 1:
        #     MSG = 'ServiceEvent({:s}) skipped, unable to identify on which topology to insert it'
        #     str_service_event = grpc_message_to_json_string(service_event)
        #     LOGGER.warning(MSG.format(str_service_event))
        #     return False

        # domain_name = topology_names.pop()  # trans-pkt/agg-net/e2e-net
        # set_mock_simap(self._simap_client, domain_name)

        #domain_topo = self._simap_client.network(domain_name)
        #domain_topo.update()

        #src_device   = self._object_cache.get(CachedEntities.DEVICE,   endpoint_uuids[0][0], force_update =True )
        #src_endpoint = self._object_cache.get(CachedEntities.ENDPOINT, *(endpoint_uuids[0]), auto_retrieve=False)
        #dst_device   = self._object_cache.get(CachedEntities.DEVICE,   endpoint_uuids[1][0], force_update =True )
        #dst_endpoint = self._object_cache.get(CachedEntities.ENDPOINT, *(endpoint_uuids[1]), auto_retrieve=False)

        #try:
        #    if src_device is None:
        #        MSG = 'Device({:s}) not found in cache'
        #        raise Exception(MSG.format(str(endpoint_uuids[0][0])))
        #    if src_endpoint is None:
        #        MSG = 'Endpoint({:s}) not found in cache'
        #        raise Exception(MSG.format(str(endpoint_uuids[0])))
        #    if dst_device is None:
        #        MSG = 'Device({:s}) not found in cache'
        #        raise Exception(MSG.format(str(endpoint_uuids[1][0])))
        #    if dst_endpoint is None:
        #        MSG = 'Endpoint({:s}) not found in cache'
        #        raise Exception(MSG.format(str(endpoint_uuids[1])))
        #except Exception as e:
        #    MSG = '{:s} in Service({:s})'
        #    raise Exception(MSG.format(str(e), grpc_message_to_json_string(service))) from e

        #src_dev_name = src_device.name
        #src_ep_name  = src_endpoint.name
        #dst_dev_name = dst_device.name
        #dst_ep_name  = dst_endpoint.name

        #parent_domain_name = DEFAULT_TOPOLOGY_NAME      # TODO: compute from service settings

        #site_1_name = 'site1'                           # TODO: compute from service settings
        #site_1 = domain_topo.node(site_1_name)
        #site_1.update(supporting_node_ids=[(parent_domain_name, src_dev_name)])
        #site_1_tp = site_1.termination_point(src_ep_name)
        #site_1_tp.update(supporting_termination_point_ids=[(parent_domain_name, src_dev_name, src_ep_name)])

        #site_2_name = 'site2'                           # TODO: compute from service settings
        #site_2 = domain_topo.node(site_2_name)
        #site_2.update(supporting_node_ids=[(parent_domain_name, dst_dev_name)])
        #site_2_tp = site_2.termination_point(dst_ep_name)
        #site_2_tp.update(supporting_termination_point_ids=[(parent_domain_name, dst_dev_name, dst_ep_name)])

        #link_name = '{:s}:{:s}-{:s}=={:s}-{:s}'.format(
        #    service_name, src_dev_name, src_ep_name, dst_dev_name, dst_ep_name
        #)
        #dom_link = domain_topo.link(link_name)
        #dom_link.update(src_dev_name, src_ep_name, dst_dev_name, dst_ep_name)

        
        #resources = Resources()
        #sampling_interval = 1.0
        #self._telemetry_pool.start_synthesizer(domain_name, resources, sampling_interval)
        return True


    def dispatch_service_create(self, service_event : ServiceEvent) -> None:
        if not self._dispatch_service_set(service_event): return

        MSG = 'Logical Link Created for Service: {:s}'
        LOGGER.info(MSG.format(grpc_message_to_json_string(service_event)))


    def dispatch_service_update(self, service_event : ServiceEvent) -> None:
        if not self._dispatch_service_set(service_event): return

        MSG = 'Logical Link Updated for Service: {:s}'
        LOGGER.info(MSG.format(grpc_message_to_json_string(service_event)))


    def dispatch_service_remove(self, service_event : ServiceEvent) -> None:
        MSG = 'Processing Service Event: {:s}'
        LOGGER.info(MSG.format(grpc_message_to_json_string(service_event)))

        service_uuid = service_event.service_id.service_uuid.uuid
        service = self._object_cache.get(CachedEntities.SERVICE, service_uuid)
        service_name = service.name

        try:
            uuid.UUID(hex=service_name)
            # skip it if properly parsed, means it is a service with a UUID-based name, i.e., a sub-service
            MSG = 'ServiceEvent({:s}) skipped, it is a subservice: {:s}'
            str_service_event = grpc_message_to_json_string(service_event)
            str_service = grpc_message_to_json_string(service)
            LOGGER.warning(MSG.format(str_service_event, str_service))
            return False
        except: # pylint: disable=bare-except
            pass

        #topology_uuid, endpoint_uuids = get_service_endpoint(service)
        #if topology_uuid is None:
        #    MSG = 'ServiceEvent({:s}) skipped, no endpoint_ids to identify topology: {:s}'
        #    str_service_event = grpc_message_to_json_string(service_event)
        #    str_service = grpc_message_to_json_string(service)
        #    LOGGER.warning(MSG.format(str_service_event, str_service))
        #    return

        topologies = self._object_cache.get_all(CachedEntities.TOPOLOGY, fresh=False)
        topology_names = {t.name for t in topologies}
        topology_names.discard(DEFAULT_TOPOLOGY_NAME)
        if len(topology_names) != 1:
            MSG = 'ServiceEvent({:s}) skipped, unable to identify on which topology to insert it'
            str_service_event = grpc_message_to_json_string(service_event)
            LOGGER.warning(MSG.format(str_service_event))
            return

        domain_name = topology_names.pop()  # trans-pkt/agg-net/e2e-net
        # delete_mock_simap(self._simap_client, domain_name)

        #domain_topo = self._simap_client.network(domain_name)
        #domain_topo.update()

        #src_device   = self._object_cache.get(CachedEntities.DEVICE,   endpoint_uuids[0][0], force_update =True )
        #src_endpoint = self._object_cache.get(CachedEntities.ENDPOINT, *(endpoint_uuids[0]), auto_retrieve=False)
        #dst_device   = self._object_cache.get(CachedEntities.DEVICE,   endpoint_uuids[1][0], force_update =True )
        #dst_endpoint = self._object_cache.get(CachedEntities.ENDPOINT, *(endpoint_uuids[1]), auto_retrieve=False)

        #try:
        #    if src_device is None:
        #        MSG = 'Device({:s}) not found in cache'
        #        raise Exception(MSG.format(str(endpoint_uuids[0][0])))
        #    if src_endpoint is None:
        #        MSG = 'Endpoint({:s}) not found in cache'
        #        raise Exception(MSG.format(str(endpoint_uuids[0])))
        #    if dst_device is None:
        #        MSG = 'Device({:s}) not found in cache'
        #        raise Exception(MSG.format(str(endpoint_uuids[1][0])))
        #    if dst_endpoint is None:
        #        MSG = 'Endpoint({:s}) not found in cache'
        #        raise Exception(MSG.format(str(endpoint_uuids[1])))
        #except Exception as e:
        #    MSG = '{:s} in Service({:s})'
        #    raise Exception(MSG.format(str(e), grpc_message_to_json_string(service))) from e

        #src_dev_name = src_device.name
        #src_ep_name  = src_endpoint.name
        #dst_dev_name = dst_device.name
        #dst_ep_name  = dst_endpoint.name

        #link_name = '{:s}:{:s}-{:s}=={:s}-{:s}'.format(
        #    service_name, src_dev_name, src_ep_name, dst_dev_name, dst_ep_name
        #)
        #te_link = domain_topo.link(link_name)
        #te_link.delete()

        #self._object_cache.delete(CachedEntities.SERVICE, service_uuid)
        #self._object_cache.delete(CachedEntities.SERVICE, service_name)

        #self._telemetry_pool.stop_worker(WorkerTypeEnum.SYNTHESIZER, domain_name)

        MSG = 'Logical Link Removed for Service: {:s}'
        LOGGER.info(MSG.format(grpc_message_to_json_string(service_event)))

#   ----- Connection Events -----

    def dispatch_connection_set(self, connection_event : ConnectionEvent) -> bool:
        MSG = 'Processing Connection Event: {:s}'
        LOGGER.info(MSG.format(grpc_message_to_json_string(connection_event)))

        # Extract connection UUID from event
        connection_uuid = connection_event.connection_id.connection_uuid.uuid

        # Clean up any stale mapping for this connection (e.g., if connection is being re-created)
        old_mapping = self._object_cache.get(CachedEntities.CONNECTION, connection_uuid, auto_retrieve=False)
        if old_mapping is not None and isinstance(old_mapping, dict) and 'domain' in old_mapping:
            self._object_cache.delete(CachedEntities.CONNECTION, connection_uuid)
            LOGGER.debug('Removed stale mapping for connection {:s} before processing'.format(connection_uuid))

        try:
            # Use common helper to prepare connection data
            result = self._prepare_connection_processing(connection_uuid)
            if result is None:
                return False
            (domain_name, processed_links) = result

            # Update telemetry for each link involved in this connection
            for link_uuid, link_name, link_topology_name in processed_links:
                # Count active connections on this link
                active_conn_count = self._count_active_connections(link_uuid, domain_name)
                LOGGER.info('Connection {:s} uses allowed link: {:s} (uuid: {:s})'.format(connection_uuid, link_name, link_uuid))
                worker_name = '{:s}:{:s}'.format(link_topology_name, link_name)

                # --- TEMPORTYY: Check for special triggering rules for L6 in trans-pkt domain ---
                if link_name == "L6":
                    # Check for special triggering rules (e.g., L6 triggers L3 and L13)
                    triggered_links = self._check_and_trigger_additional_links(
                                                link_topology_name, active_conn_count)
                                # Update the cached mapping to include triggered links
                    if triggered_links:
                        mapping = self._object_cache.get(CachedEntities.CONNECTION, connection_uuid, auto_retrieve=False)
                        if mapping and isinstance(mapping, dict):
                            mapping['triggered_links'] = triggered_links
                            self._object_cache.set(CachedEntities.CONNECTION, mapping, connection_uuid)
                            LOGGER.debug('Updated connection {:s} mapping with {:d} triggered links'.format(
                                connection_uuid, len(triggered_links)))
                # --- END OF TEMPORARY LOGIC ---

                # Worker should already exist from _dispatch_link_set (link creation event)
                if not self._telemetry_pool.has_worker(WorkerTypeEnum.SYNTHESIZER, worker_name):
                    LOGGER.warning('Worker not found for link {:s}, creating and starting new worker'.format(link_name))
                    
                    # Create worker with same parameters as in _dispatch_link_set
                    resources = Resources()
                    resources.links.append(ResourceLink(
                        domain_name = link_topology_name,
                        link_name   = link_name,
                        metrics_sampler = SyntheticSampler.create_random(
                            connection_count = active_conn_count,
                            link_capacity    = LINKS_CAPACITY.get(link_name, 100.0)
                        ),
                        related_service_ids=[],     # TODO: populate with actual related services if needed (later)
                    ))
                    sampling_interval = 1.0
                    self._telemetry_pool.start_synthesizer(worker_name, resources, sampling_interval)
                    LOGGER.info('Started new synthesizer worker: {:s}'.format(worker_name))
                else:
                    # Worker exists, update connection count for congestion simulation
                    worker = self._telemetry_pool.get_worker(WorkerTypeEnum.SYNTHESIZER, worker_name)
                    assert isinstance(worker, SynthesizerWorker), \
                        'Expected SynthesizerWorker, got {:s}'.format(type(worker).__name__)
                    
                    worker.change_resources(active_conn_count)
                    LOGGER.info('Updated telemetry of already running worker: link {:s}, connection_count={:d}'.format(
                        link_name, active_conn_count))

        except Exception as e:
            LOGGER.exception('Failed to process connection event {:s}: {:s}'.format(connection_uuid, str(e)))
            return False

        return True

    # TEMPORARY: This function implements the special triggering rules for L6 in trans-pkt domain. 
    def _check_and_trigger_additional_links(
            self, link_topology_name: str, active_conn_count: int
        ) -> List[Tuple[str, str, str]]:
        """
        Check for special triggering rules and start additional workers.
        
        Rule: When L6 is processed in trans-pkt domain, also start workers for L3 and L13.
        
        Args:
            connection_uuid: UUID of the connection being processed
            domain_name: Domain name (e.g., 'trans-pkt')
            processed_links: List of (link_uuid, link_name, link_topology_name) already processed
        
        Returns:
            List of triggered links with format: (link_uuid, link_name, topology_name)
        """
        triggered_links = []
        
        # Trigger workers for L3 and L13 using same topology as L6
        for link_name in ['L3', 'L13']:
            # Generate UUID for the triggered link
            link_uuid   = str(uuid.uuid4())
            worker_name = '{:s}:{:s}'.format(link_topology_name, link_name)
            
            LOGGER.info('Triggering worker for link {:s} (generated uuid: {:s})'.format(link_name, link_uuid))
            
            # Check if worker already exists
            if not self._telemetry_pool.has_worker(WorkerTypeEnum.SYNTHESIZER, worker_name):
                # Create and start worker
                resources = Resources()
                resources.links.append(ResourceLink(
                    domain_name = link_topology_name,
                    link_name   = link_name,
                    metrics_sampler = SyntheticSampler.create_random(
                        connection_count = active_conn_count,
                        link_capacity    = LINKS_CAPACITY.get(link_name, 100.0)
                    ),
                    related_service_ids = [],
                ))
                sampling_interval = 1.0
                self._telemetry_pool.start_synthesizer(worker_name, resources, sampling_interval)
                LOGGER.info('Started triggered synthesizer worker: {:s}'.format(worker_name))
            else:
                LOGGER.info('Worker {:s} already exists, skipping creation'.format(worker_name))
            
            triggered_links.append((link_uuid, link_name, link_topology_name))
        
        return triggered_links


    def _prepare_connection_processing(self, connection_uuid: str):
        """
        Extract common logic for processing connection events.

        Returns:
            Tuple of ( domain_name, processed_links) or None if failed
        """
        # Get the connection object
        connection = self._object_cache.get(CachedEntities.CONNECTION, connection_uuid)
        if connection is None:
            LOGGER.warning('Connection {:s} not found in cache'.format(connection_uuid))
            return None

        MSG = 'Processing Connection: {:s}'
        LOGGER.info(MSG.format(grpc_message_to_json_string(connection)))

        _, link_uuids = get_connection_endpoints_and_links(connection_uuid)

        # Determine the controller's domain name (network_id)
        topologies = self._object_cache.get_all(CachedEntities.TOPOLOGY, fresh=False)
        topology_names = {t.name for t in topologies}
        topology_names.discard(DEFAULT_TOPOLOGY_NAME)
        if len(topology_names) != 1:
            LOGGER.warning('Unable to identify self-controller for connection {:s} and {!r}'.format(connection_uuid, topology_names))
            return None
        domain_name = topology_names.pop()
        
        # Call set_simap_network with proper parameters
        network_connection = grpc_message_to_json(connection)
        set_simap_network(self._context_client, self._simap_client, domain_name, network_connection)
        LOGGER.info('Set SIMAP network for connection {:s} in domain {:s}'.format(connection_uuid, domain_name))

        # Filter links based on ALLOWED_LINKS_PER_CONTROLLER
        allowed_link_names = ALLOWED_LINKS_PER_CONTROLLER.get(domain_name, set())
        LOGGER.debug('Allowed links for domain {:s}: {:s}'.format(domain_name, str(allowed_link_names)))
        processed_links = []
        for link_uuid in link_uuids:
            link = self._object_cache.get(CachedEntities.LINK, link_uuid)
            if link.name in allowed_link_names:
                # Get the link's topology for worker naming
                link_topology_uuid, _ = get_link_endpoint(link)
                link_topology         = self._object_cache.get(CachedEntities.TOPOLOGY, link_topology_uuid)
                processed_links.append((link_uuid, link.name, link_topology.name))

        if not processed_links:
            LOGGER.debug('Connection {:s} has no allowed links for domain {:s}'.format(
                connection_uuid, domain_name))
            self._object_cache.delete(CachedEntities.CONNECTION, connection_uuid)
            return None

        # Cache the connection-to-links mapping for later retrieval (e.g., during REMOVE events)
        mapping = {
            'domain': domain_name,
            'links': {link_uuid: {'name': link_name, 'topology': link_topo_name} for link_uuid, link_name, link_topo_name in processed_links},
            'triggered_links': []  # Will store additional links triggered by special rules
        }
        self._object_cache.set(CachedEntities.CONNECTION, mapping, connection_uuid)
        LOGGER.debug('Cached connection {:s} mapping with {:d} links for domain {:s}'.format(
            connection_uuid, len(processed_links), domain_name))

        return domain_name, processed_links


    def _count_active_connections(self, link_uuid: str, domain_name: str, ) -> int:
        """
        Count active connections using a specific link.

        Args:
            link_uuid: UUID of the link to count connections for
            domain_name: Domain name to filter connections
        Returns:
            int: Number of active connections using this link
        """

        all_cached_connections = self._object_cache.get_all(CachedEntities.CONNECTION, fresh=False)
        active_count = 0
        for cached_obj in all_cached_connections:
            if not isinstance(cached_obj, dict) or 'domain' not in cached_obj or 'links' not in cached_obj:
                continue
            
            if cached_obj['domain'] != domain_name:
                continue
            
            if link_uuid in cached_obj['links']:
                active_count += 1

        LOGGER.info('Active connection count on link {:s} in domain {:s}: {:d}'.format(
            link_uuid, domain_name, active_count))
        return active_count


    def dispatch_connection_create(self, connection_event : ConnectionEvent) -> None:
        if not self.dispatch_connection_set(connection_event): return

        MSG = 'Skipping Connection Create Event: {:s}'
        LOGGER.debug(MSG.format(grpc_message_to_json_string(connection_event)))


    def dispatch_connection_update(self, connection_event : ConnectionEvent) -> None:
        if not self.dispatch_connection_set(connection_event): return

        MSG = 'Skipping Connection Update Event: {:s}'
        LOGGER.debug(MSG.format(grpc_message_to_json_string(connection_event)))


    def dispatch_connection_remove(self, connection_event : ConnectionEvent) -> None:
        MSG = 'Processing Connection Remove Event: {:s}'
        LOGGER.info(MSG.format(grpc_message_to_json_string(connection_event)))

        connection_uuid = connection_event.connection_id.connection_uuid.uuid

        try:
            mapping = self._object_cache.get(CachedEntities.CONNECTION, connection_uuid, auto_retrieve=False)
            LOGGER.info('Retrieved mapping for connection {:s}: {:s}'.format(connection_uuid, str(mapping)))
            if mapping is None:
                MSG = 'Connection {:s} not managed by this controller (not in allowed links), skipping removal'
                LOGGER.debug(MSG.format(connection_uuid))
                return
            
            # Defensive: distinguish mapping dicts from potential protobuf Connection objects
            elif not isinstance(mapping, dict) or 'domain' not in mapping or 'links' not in mapping:
                MSG = 'Invalid mapping structure for connection {:s}: expected dict with domain/links keys'
                raise Exception(MSG.format(connection_uuid))
            
            # Extract domain and links from cached mapping
            domain_name     = mapping['domain']
            link_uuids_dict = mapping['links']
            processed_links = [(link_uuid, link_data['name'], link_data['topology']) for link_uuid, link_data in link_uuids_dict.items()]
            
            LOGGER.info('Retrieved cached mapping for connection {:s}: domain={:s}, links={:d}'.format(
                connection_uuid, domain_name, len(processed_links)))

            # Delete the connection from cache first (we already have the mapping)
            self._object_cache.delete(CachedEntities.CONNECTION, connection_uuid)
            LOGGER.debug('Deleted cached mapping for connection {:s}'.format(connection_uuid))

            # Process each link: count remaining connections and stop/update worker accordingly
            all_links_stopped = True  # Track if all links have been stopped
            for link_uuid, link_name, link_topology_name in processed_links:
                worker_name = '{:s}:{:s}'.format(link_topology_name, link_name)

                if not self._telemetry_pool.has_worker(WorkerTypeEnum.SYNTHESIZER, worker_name):
                    LOGGER.warning('Worker not found for link {:s}, skipping telemetry update for connection removal'.format(link_name))
                    continue
                
                # Count remaining connections on this link (now excluding the deleted one)
                remaining_conn_count = self._count_active_connections(link_uuid, domain_name)
                
                if remaining_conn_count == 0:
                    # No other connections use this link, stop the worker
                    self._telemetry_pool.stop_worker(WorkerTypeEnum.SYNTHESIZER, worker_name)
                    LOGGER.info('Stopped telemetry worker for link {:s}, no connections remain'.format(link_name))

                    # ---- TEMPORARY: Stop triggered links (L3 and L13 when L6 is removed from trans-pkt) ----
                    if link_name == "L6":
                        try:
                            triggered_links = mapping.get('triggered_links', [])
                            if triggered_links:
                                LOGGER.info('Connection {:s} has {:d} triggered links to clean up'.format(
                                    connection_uuid, len(triggered_links)))
                                
                                for _, trig_link_name, trig_link_topology_name in triggered_links:
                                    trig_worker_name = '{:s}:{:s}'.format(trig_link_topology_name, trig_link_name)
                                    
                                    if self._telemetry_pool.has_worker(WorkerTypeEnum.SYNTHESIZER, trig_worker_name):
                                        self._telemetry_pool.stop_worker(WorkerTypeEnum.SYNTHESIZER, trig_worker_name)
                                        LOGGER.info('Stopped triggered telemetry worker for link {:s}'.format(trig_link_name))
                                    else:
                                        LOGGER.warning('Triggered worker {:s} not found during cleanup'.format(trig_worker_name))
                        except Exception as e:
                            LOGGER.exception('Failed to stop triggered links for connection {:s}: {:s}'.format(connection_uuid, str(e)))
                    # ---- END OF TEMPORARY LOGIC ----
                else:
                    # Other connections still use this link, update worker with new count
                    all_links_stopped = False
                    worker = self._telemetry_pool.get_worker(WorkerTypeEnum.SYNTHESIZER, worker_name)
                    assert isinstance(worker, SynthesizerWorker), \
                        'Expected SynthesizerWorker, got {:s}'.format(type(worker).__name__)
                    
                    worker.change_resources(remaining_conn_count)
                    LOGGER.info('Updated telemetry for link {:s} after connection removal, {:d} connections remain'.format(
                        link_name, remaining_conn_count))

            # Delete SIMAP network only if all links have been stopped
            if all_links_stopped:
                delete_simap_network(self._simap_client, domain_name)
                LOGGER.info('Deleted SIMAP network for domain {:s} after all links stopped'.format(domain_name))
            else:
                LOGGER.debug('SIMAP network {:s} retained, some links still have active connections'.format(domain_name))

        except Exception as e:
            LOGGER.exception('Failed to process connection removal {:s}: {:s}'.format(
                connection_uuid, str(e)))
    

class SimapUpdater:
    def __init__(
        self, simap_client : SimapClient, telemetry_pool : TelemetryPool,
        terminate : threading.Event
    ) -> None:
        self._simap_client = simap_client
        self._telemetry_pool = telemetry_pool
        self._context_client = ContextClient()

        self._event_collector = BaseEventCollector(terminate=terminate)
        self._event_collector.install_collector(
            self._context_client.GetAllEvents, Empty(), log_events_received=True
        )

        self._event_dispatcher = EventDispatcher(
            self._event_collector.get_events_queue(), self._simap_client,
            self._context_client, self._telemetry_pool, terminate=terminate
        )

    def start(self) -> None:
        self._context_client.connect()
        self._event_dispatcher.start()
        self._event_collector.start()

    def stop(self):
        self._event_collector.stop()
        self._event_dispatcher.stop()
        self._context_client.close()
