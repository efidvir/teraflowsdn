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


import pytz
import queue
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
from datetime import datetime
from telemetry.backend.service.collector_api._Collector import _Collector

from scapy.all import *
import ipaddress

from .INTCollectorCommon import IntDropReport, IntLocalReport, IntFixedReport, FlowInfo, IPPacket, UDPPacket
from common.proto.kpi_manager_pb2 import KpiId, KpiDescriptor
from confluent_kafka import Producer as KafkaProducer
from common.tools.kafka.Variables import KafkaConfig, KafkaTopic
from uuid import uuid4
from typing import Dict, List, Tuple
from datetime import datetime, timezone
import json

from kpi_manager.client.KpiManagerClient import KpiManagerClient
from context.client.ContextClient import ContextClient
from analytics.frontend.client.AnalyticsFrontendClient import AnalyticsFrontendClient
from common.proto.kpi_sample_types_pb2 import KpiSampleType
import time
import logging

LOGGER = logging.getLogger(__name__)

DEF_SW_NUM = 10

class INTCollector(_Collector):

    last_packet_time = 0.0 # Track the timestamp of the last packet
    max_idle_time = 5      # For how long we tolerate inactivity
    sniff_timeout = 3      # How often we stop sniffing to check for inactivity

    """
    INTCollector spawns a packet sniffer at the interface of the Telemetry service,
    which is mapped to the interface of the TFS host.
    INT packets arriving there are:
    - picked up by the INT collector
    - parsed, and
    - telemetry KPI metric values are extracted and reported to Kafka as KPIDescriptors
    """

    def __init__(self, address: str, port: int, **settings) -> None:
        super().__init__('INTCollector', address, port, **settings)
        self.collector_id = settings.pop('collector_id', None)
        self.interface = settings.pop('interface', None)
        self.kpi_id = settings.pop('kpi_id', None)
        self.service_id = settings.pop('service_id', None)
        self.context_id = settings.pop('context_id', None)

        if any(item is None for item in [
                self.collector_id, self.interface, self.kpi_id, self.service_id, self.context_id]):
            LOGGER.error("INT collector not instantiated properly: Bad input")
            return

        self._out_samples = queue.Queue()
        self._scheduler   = BackgroundScheduler(daemon=True)
        self._scheduler.configure(
            jobstores = {'default': MemoryJobStore()},
            executors = {'default': ThreadPoolExecutor(max_workers=1)},
            timezone  = pytz.utc
        )
        self.kafka_producer = KafkaProducer({'bootstrap.servers': KafkaConfig.get_kafka_address()})
        self.kpi_manager_client = KpiManagerClient()
        self.analytics_frontend_client = AnalyticsFrontendClient()
        self.context_client = ContextClient()
        self.table = {}
        self.connected = False
        LOGGER.info("=== INT Collector initialized")

    def Connect(self) -> bool:
        LOGGER.info("=== INT Collector Connect()")
        LOGGER.info(f"Connecting to {self.interface}:{self.port}")

        self._scheduler.add_job(
            self.sniff_with_restarts_on_idle,
            id=self.kpi_id,
            args=[self.interface, self.port, self.service_id]
        )

        self._scheduler.start()
        self.connected = True
        LOGGER.info(f"Successfully connected to {self.interface}:{self.port}")
        return True

    def Disconnect(self) -> bool:
        LOGGER.info("=== INT Collector Disconnect()")
        LOGGER.info(f"Disconnecting from {self.interface}:{self.port}")
        if not self.connected:
            LOGGER.warning("INT Collector is not connected. Nothing to disconnect.")
            return False

        self._scheduler.remove_job(self.kpi_id)
        self._scheduler.shutdown()

        self.connected = False
        LOGGER.info(f"Successfully disconnected from {self.interface}:{self.port}")
        return True

    def require_connection(self):
        if not self.connected:
            raise RuntimeError("INT collector is not connected. Please connect before performing operations.")

    def SubscribeState(self, subscriptions: List[Tuple[str, dict, float, float, str, int, str, str]]) -> bool:
        LOGGER.info("=== INT Collector SubscribeState()")
        self.require_connection()
        try:
            _, _, _, _, interface, port, service_id, _ = subscriptions
        except:
            LOGGER.exception(f"Invalid subscription format: {subscriptions}")
            return False

        if self.kpi_id:
            self._scheduler.add_job(
                self.sniff_with_restarts_on_idle,
                id=self.kpi_id,
                args=[interface, port, service_id]
            )

        return True

    def UnsubscribeState(self, resource_key: str) -> bool:
        LOGGER.info("=== INT Collector UnsubscribeState()")
        self.require_connection()
        try: 
            # Check if job exists
            job_ids = [job.id for job in self._scheduler.get_jobs() if resource_key in job.id]
            if not job_ids:
                LOGGER.warning(f"No active jobs found for {resource_key}. It might have already been terminated.")
                return False
            for job_id in job_ids:
                self._scheduler.remove_job(job_id)
            LOGGER.info(f"Unsubscribed from {resource_key} with job IDs: {job_ids}")
            return True
        except:
            LOGGER.exception(f"Failed to unsubscribe from {resource_key}")
            return False

    def on_idle_timeout(self):
        LOGGER.info(f"=== INT Collector IDLE() - No INT packets arrived during the last {self.max_idle_time} seconds")
        LOGGER.debug(f"last_packet_time {self.last_packet_time} seconds")

        # Report a zero value for the P4 switch KPIs
        values = [0]
        for sw_id in range(1, DEF_SW_NUM+1):
            sw = self.table.get(sw_id)
            self.overwrite_switch_values(sw, values)

    def overwrite_switch_values(self, switch, values):
        if not switch:
            return

        # Overwrite values using zip
        for key, new_value in zip(switch, values):
            switch[key] = new_value

        for key, value in switch.items():
            self.send_message_to_kafka(key, value)

    def process_packet(self, packet, port, service_id):
        LOGGER.debug("=== INT Collector Packet-In()")
        LOGGER.debug(packet)

        # Check for IP header
        if IP not in packet:
            return None
        ip_layer = packet[IP]

        # IP parsing
        try:
            ihl = ip_layer.ihl * 4
            raw_ip = bytes(ip_layer)
            ip_pkt = IPPacket(raw_ip[:ihl]) # exclude options if any
            src_ip_str = str(ipaddress.IPv4Address(ip_pkt.ip_src))
            dst_ip_str = str(ipaddress.IPv4Address(ip_pkt.ip_dst))
            # ip_pkt.show()
        except Exception as ex:
            LOGGER.exception(f"Failed to parse IP packet: {ex}")
            return None

        LOGGER.debug(f"ip src: {src_ip_str}")
        LOGGER.debug(f"ip dst: {dst_ip_str}")
        LOGGER.debug(f"ip-proto: {ip_pkt.ip_proto}")

        # Check for UDP header
        if UDP not in ip_layer:
            return None
        udp_layer = ip_layer[UDP]

        # We care about datagrams arriving on the INT port
        if udp_layer.dport != port:
            LOGGER.warning(f"Expected UDP INT packet on port {udp_layer.dport}. Received packet on port {port}")
            return None

        try:
            raw_udp = bytes(udp_layer)
            udp_dgram = UDPPacket(raw_udp)
            # udp_dgram.show()
        except Exception as ex:
            LOGGER.exception(f"Failed to parse UDP datagram: {ex}")
            return None

        # UDP parsing
        LOGGER.debug(f"port src: {udp_dgram.udp_port_src}")
        LOGGER.debug(f"port dst: {udp_dgram.udp_port_dst}")

        # Get the INT report data (after UDP header)
        int_data = bytes(udp_layer.payload)

        # Parse fixed report (first 20 bytes)
        offset = 20
        fixed_report = IntFixedReport(int_data[:offset])
        # fixed_report.show()

        drop_report = None
        local_report = None
        lat = 0

        # Drop report
        if fixed_report.d == 1:
            drop_report = IntDropReport(int_data[offset:offset + 4])
            offset += 4
            # drop_report.show()
        # Regular report
        elif fixed_report.f == 1 or fixed_report.q == 1:
            local_report = IntLocalReport(int_data[offset:offset + 8])
            offset += 8
            lat = local_report.egress_timestamp - fixed_report.ingress_timestamp
            assert lat > 0, f"Egress timestamp must be > ingress timestamp. Got a diff: {lat}"
            # local_report.show()

        # Create flow info
        flow_info = FlowInfo(
            src_ip=ip_pkt.ip_src,
            dst_ip=ip_pkt.ip_dst,
            src_port=udp_layer.sport,
            dst_port=udp_layer.dport,
            ip_proto=ip_layer.proto,
            flow_sink_time=fixed_report.ingress_timestamp,
            num_int_hop=1,
            seq_num=fixed_report.seq_num,
            switch_id=fixed_report.switch_id,
            ingress_timestamp=fixed_report.ingress_timestamp,
            ingress_port_id=fixed_report.ingress_port_id,
            egress_port_id=fixed_report.egress_port_id,
            queue_id=local_report.queue_id if local_report else 0,
            queue_occupancy=local_report.queue_occupancy if local_report else 0,
            egress_timestamp=local_report.egress_timestamp if local_report else 0,
            is_drop=1 if drop_report else 0,
            drop_reason=drop_report.drop_reason if drop_report else 0,
            hop_latency=lat
        )
        LOGGER.debug(f"Flow info: {flow_info}")

        self.create_descriptors_and_send_to_kafka(flow_info, service_id)
        self.last_packet_time = time.time()

        return flow_info

    def set_kpi_descriptor(self, kpi_uuid, service_id, sample_type):
        kpi_descriptor = KpiDescriptor()
        kpi_descriptor.kpi_sample_type = sample_type
        kpi_descriptor.service_id.service_uuid.uuid = service_id
        kpi_descriptor.kpi_id.kpi_id.uuid = kpi_uuid

        try:
            kpi_id: KpiId = self.kpi_manager_client.SetKpiDescriptor(kpi_descriptor)
        except Exception as ex:
            LOGGER.exception(f"Failed to set KPI descriptor {kpi_uuid}: {ex}")

        return kpi_id

    def create_descriptors_and_send_to_kafka(self, flow_info, service_id):
        LOGGER.debug(f"Packet from switch: {flow_info.switch_id} with latency: {flow_info.hop_latency}")
        if(self.table.get(flow_info.switch_id) == None):
            seq_num_kpi_id     = str(uuid4())
            ingress_ts_kpi_id  = str(uuid4())
            egress_ts_kpi_id   = str(uuid4())
            hop_lat_kpi_id     = str(uuid4())
            ing_port_id_kpi_id = str(uuid4())
            egr_port_id_kpi_id = str(uuid4())
            queue_occup_kpi_id = str(uuid4())
            is_drop_kpi_id     = str(uuid4())
            sw_lat_kpi_id      = str(uuid4())

            LOGGER.debug(f"seq_num_kpi_id     for switch {flow_info.switch_id}: {seq_num_kpi_id}")
            LOGGER.debug(f"ingress_ts_kpi_id  for switch {flow_info.switch_id}: {ingress_ts_kpi_id}")
            LOGGER.debug(f"egress_ts_kpi_id   for switch {flow_info.switch_id}: {egress_ts_kpi_id}")
            LOGGER.debug(f"hop_lat_kpi_id     for switch {flow_info.switch_id}: {hop_lat_kpi_id}")
            LOGGER.debug(f"ing_port_id_kpi_id for switch {flow_info.switch_id}: {ing_port_id_kpi_id}")
            LOGGER.debug(f"egr_port_id_kpi_id for switch {flow_info.switch_id}: {egr_port_id_kpi_id}")
            LOGGER.debug(f"queue_occup_kpi_id for switch {flow_info.switch_id}: {queue_occup_kpi_id}")
            LOGGER.debug(f"is_drop_kpi_id     for switch {flow_info.switch_id}: {is_drop_kpi_id}")
            LOGGER.debug(f"sw_lat_kpi_id      for switch {flow_info.switch_id}: {sw_lat_kpi_id}")

            seq_num_kpi           = self.set_kpi_descriptor(seq_num_kpi_id,     service_id ,KpiSampleType.KPISAMPLETYPE_INT_SEQ_NUM)
            ingress_timestamp_kpi = self.set_kpi_descriptor(ingress_ts_kpi_id,  service_id, KpiSampleType.KPISAMPLETYPE_INT_TS_ING)
            egress_timestamp_kpi  = self.set_kpi_descriptor(egress_ts_kpi_id,   service_id, KpiSampleType.KPISAMPLETYPE_INT_TS_EGR)
            hop_latency_kpi       = self.set_kpi_descriptor(hop_lat_kpi_id,     service_id, KpiSampleType.KPISAMPLETYPE_INT_HOP_LAT)
            ingress_port_id_kpi   = self.set_kpi_descriptor(ing_port_id_kpi_id, service_id, KpiSampleType.KPISAMPLETYPE_INT_PORT_ID_ING)
            egress_port_id_kpi    = self.set_kpi_descriptor(egr_port_id_kpi_id, service_id, KpiSampleType.KPISAMPLETYPE_INT_PORT_ID_EGR)
            queue_occup_kpi       = self.set_kpi_descriptor(queue_occup_kpi_id, service_id, KpiSampleType.KPISAMPLETYPE_INT_QUEUE_OCCUP)
            is_drop_kpi           = self.set_kpi_descriptor(is_drop_kpi_id,     service_id, KpiSampleType.KPISAMPLETYPE_INT_IS_DROP)

            # Set a dedicated KPI descriptor for every switch
            sw_lat_kpi = None
            sw_sample_types = [
                KpiSampleType.KPISAMPLETYPE_INT_HOP_LAT_SW01, KpiSampleType.KPISAMPLETYPE_INT_HOP_LAT_SW02,
                KpiSampleType.KPISAMPLETYPE_INT_HOP_LAT_SW03, KpiSampleType.KPISAMPLETYPE_INT_HOP_LAT_SW04,
                KpiSampleType.KPISAMPLETYPE_INT_HOP_LAT_SW05, KpiSampleType.KPISAMPLETYPE_INT_HOP_LAT_SW06,
                KpiSampleType.KPISAMPLETYPE_INT_HOP_LAT_SW07, KpiSampleType.KPISAMPLETYPE_INT_HOP_LAT_SW08,
                KpiSampleType.KPISAMPLETYPE_INT_HOP_LAT_SW09, KpiSampleType.KPISAMPLETYPE_INT_HOP_LAT_SW10
            ]
            for i, sw_id in enumerate(range(1, DEF_SW_NUM+1)):
                if flow_info.switch_id == sw_id:
                    LOGGER.debug(f"Set latency KPI for switch {flow_info.switch_id}: {sw_lat_kpi_id}")
                    sw_lat_kpi = self.set_kpi_descriptor(sw_lat_kpi_id, service_id, sw_sample_types[i])

            # Gather keys and values
            keys   = [
                seq_num_kpi.kpi_id.uuid,
                ingress_timestamp_kpi.kpi_id.uuid,
                egress_timestamp_kpi.kpi_id.uuid,
                hop_latency_kpi.kpi_id.uuid,
                ingress_port_id_kpi.kpi_id.uuid,
                egress_port_id_kpi.kpi_id.uuid,
                queue_occup_kpi.kpi_id.uuid,
                is_drop_kpi.kpi_id.uuid,
                sw_lat_kpi.kpi_id.uuid
            ]
            values = [
                flow_info.seq_num,
                flow_info.ingress_timestamp,
                flow_info.egress_timestamp,
                flow_info.hop_latency,
                flow_info.ingress_port_id,
                flow_info.egress_port_id,
                flow_info.queue_occupancy,
                flow_info.is_drop,
                flow_info.hop_latency
            ]
            assert len(keys) == len(values), "KPI keys and values must agree"
            switch = {keys[i]: values[i] for i in range(len(keys))}

            self.table[flow_info.switch_id] = switch

            # Dispatch to Kafka
            for key, value in switch.items():
                self.send_message_to_kafka(key, value)
        else:
            values = [
                flow_info.seq_num,
                flow_info.ingress_timestamp,
                flow_info.egress_timestamp,
                flow_info.hop_latency,
                flow_info.ingress_port_id,
                flow_info.egress_port_id,
                flow_info.queue_occupancy,
                flow_info.is_drop,
                flow_info.hop_latency
            ]
            switch = self.table.get(flow_info.switch_id)

            # Overwrite values using zip
            self.overwrite_switch_values(switch, values)

    def send_message_to_kafka(self, kpi_id, measured_kpi_value):
        LOGGER.debug("=== INT Collector Kafka Writer()")
        producer = self.kafka_producer
        kpi_value: Dict = {
            "time_stamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "kpi_id": kpi_id,
            "kpi_value": measured_kpi_value
        }
        try:
            producer.produce(
                KafkaTopic.VALUE.value,
                key=self.collector_id,
                value=json.dumps(kpi_value),
                callback=self.delivery_callback
            )
            producer.flush()
        except Exception as ex:
            LOGGER.error(f"Message with kpi_id: {kpi_id} is NOT sent to kafka!")
            LOGGER.exception(f"{ex}")
            return
        LOGGER.debug(f"Message with kpi_id: {kpi_id} is sent to kafka!")

    def packet_callback(self, packet, port, service_id):
        flow_info = self.process_packet(packet, port, service_id)
        if flow_info:
            LOGGER.debug(f"Flow info: {flow_info}")

    def sniff_with_restarts_on_idle(self, interface, port, service_id):
        LOGGER.info("=== INT Collector Sniffer Start")
        while True:
            # Run sniff for a short period to periodically check for idle timeout
            try:
                sniff( # type: ignore
                    iface=interface,
                    filter=f"udp port {port}",
                    prn=lambda pkt: self.packet_callback(pkt, port, service_id),
                    timeout=self.sniff_timeout
                )
            except Exception as ex:
                LOGGER.exception(ex)
                self.Disconnect()

            if not self.connected:
                break

            # Check if idle period has been exceeded
            now = time.time()
            LOGGER.debug(f"Time now: {self.epoch_to_day_time(now)}")
            LOGGER.debug(f"Time last pkt: {self.epoch_to_day_time(self.last_packet_time)}")
            diff = now - self.last_packet_time
            assert diff > 0, f"Time diff: {diff} sec must be positive"
            if (now - self.last_packet_time) > self.max_idle_time:
                self.on_idle_timeout()
                self.last_packet_time = now  # Reset timer after action
        LOGGER.info("=== INT Collector Sniffer End")

    def delivery_callback(self, err, msg):
        if err:
            LOGGER.error(f"Kafka message delivery failed: {str(err)}")

    def epoch_to_day_time(self, ep_time : float):
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ep_time))
