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

import time
import json
import threading
import logging

from confluent_kafka                            import KafkaException, KafkaError
from common.tools.kafka.Variables               import KafkaTopic
from analytics.backend.service.AnalyzerHandlers import Handlers, select_handler, aggregation_handler
from analytics.backend.service.AnalyzerHelper   import AnalyzerHelper

logger = logging.getLogger(__name__)

class DaskStreamer(threading.Thread):
    def __init__(
        self, key, input_kpis, output_kpis, thresholds,
        batch_size        = 5,
        batch_duration    = None,
        window_size       = None,
        cluster_instance  = None,
        producer_instance = AnalyzerHelper.initialize_kafka_producer()
    ) -> None:
        super().__init__()
        self.key            = key
        self.input_kpis     = input_kpis
        self.output_kpis    = output_kpis
        self.thresholds     = thresholds
        self.window_size    = window_size      # TODO: Not implemented
        self.batch_size     = batch_size
        self.batch_duration = batch_duration
        self.running        = True
        self.batch          = []

        logger.info(f"Dask Streamer            key: {self.key}")
        logger.info(f"Dask Streamer    input  KPIs: {self.input_kpis}")
        logger.info(f"Dask Streamer    output KPIs: {self.output_kpis}")
        logger.info(f"Dask Streamer     thresholds: {self.thresholds}")
        logger.info(f"Dask Streamer    window size: {self.window_size}")
        logger.info(f"Dask Streamer     batch size: {self.batch_size}")
        logger.info(f"Dask Streamer batch duration: {self.batch_duration}")

        # Initialize Kafka and Dask components
        self.client   = AnalyzerHelper.initialize_dask_client(cluster_instance)
        self.consumer = AnalyzerHelper.initialize_kafka_consumer()      # Single-threaded consumer
        self.producer = producer_instance

        logger.info("Dask Streamer initialized.")

    def run(self):
        """Main method to start the DaskStreamer."""
        try:
            logger.info("Dask Streamer started")
            last_batch_time = time.time()
            while True:
                if not self.consumer:
                    logger.warning("Kafka consumer is not initialized or stopped. Exiting loop.")
                    break
                if not self.running:
                    logger.warning("Dask Streamer instance has been terminated. Exiting loop.")
                    break
                if not self.client:
                    logger.warning("Dask client is not running. Exiting loop.")
                    break
                message = self.consumer.poll(timeout=1.0)
                if message is None:
                    logger.debug("No new messages received.")
                    continue
                if message.error():
                    if message.error().code() == KafkaError._PARTITION_EOF:
                        logger.warning(f"Consumer reached end of topic {message.topic()}/{message.partition()}")
                    elif message.error().code() == KafkaError.UNKNOWN_TOPIC_OR_PART:
                        logger.error(f"Subscribed topic {message.topic()} does not exist. May be topic does not have any messages.")
                        continue
                    elif message.error():
                        raise KafkaException(message.error())
                else:
                    try:
                        value = json.loads(message.value())
                    except json.JSONDecodeError:
                        logger.error(f"Failed to decode message: {message.value()}")
                        continue
                    # This streamer is only meant to serve a list of input KPIs
                    if value["kpi_id"] in self.input_kpis:
                        self.batch.append(value)
                    # Ignore the rest..
                    else:
                        continue

                # Window size has a precedence over batch size
                if self.batch_duration is None:
                    if len(self.batch) >= self.batch_size:  # If batch size is not provided, process continue with the default batch size
                        logger.info(f"Processing based on batch size {self.batch_size}.")
                        self.task_handler_selector()
                        self.batch = []
                else:
                    # Process based on window size
                    current_time = time.time()
                    if (current_time - last_batch_time) >= self.batch_duration and self.batch:
                        logger.info(f"Processing based on window size {self.batch_duration}.")
                        self.task_handler_selector()
                        self.batch = []
                        last_batch_time = current_time

        except Exception as e:
            logger.exception(f"Error in Dask streaming process: {e}")
        finally:
            self.stop()
            logger.info("Exiting Dask Streamer...")

    def task_handler_selector(self):
        """Select the task handler based on the task type."""
        logger.info(f"Batch to be processed: {self.batch}")
        handler_name = self.thresholds["task_type"]
        if Handlers.is_valid_handler(handler_name):
            if self.client is not None and self.client.status == 'running':
                logger.info(f"Selecting the handler for key {self.key}")
                logger.info(f"|--> Input  KPIs {self.input_kpis}")
                logger.info(f"|--> Output KPIs {self.output_kpis}")
                logger.info(f"|--> Thresholds  {self.thresholds}")
                try:
                    handler_fn = select_handler(handler_name)
                    future = self.client.submit(
                        handler_fn,
                        self.key,
                        self.batch,
                        self.input_kpis,
                        self.output_kpis,
                        self.thresholds
                    )
                    logger.info(f"|--> Handler result  {future.result()}")
                    future.add_done_callback(
                        lambda fut: self.produce_result(fut.result(), KafkaTopic.ALARMS.value)
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to submit task to Dask client or unable to process future. See error for detail: {e}")
            else:
                logger.warning("Dask client is not running. Skipping processing.")
        else:
            logger.warning(f"Unknown task type: {self.thresholds['task_type']}. Skipping processing.")

    def produce_result(self, result, destination_topic):
        """Produce results to the Kafka topic."""
        if not result:
            logger.warning("Nothing to produce. Skipping.")
            return
        for record in result:
            # Filter out records not related with the output KPI of interest
            if record["kpi_id"] not in self.output_kpis:
                continue
            logger.info(f"Kafka Alarm - Record: {record}")
            try:
                self.producer.produce(
                    destination_topic,
                    key=str(record.get('kpi_id', '')),
                    value=json.dumps(record),
                    callback=AnalyzerHelper.delivery_report
                )
            except KafkaException as e:
                logger.error(f"Failed to produce message: {e}")
        self.producer.flush()
        logger.info(f"Produced {len(result)} aggregated records to '{destination_topic}'.")

    def stop(self):
        """Clean up Kafka and Dask thread resources."""
        if not self.running:
            logger.info("Dask Streamer is already stopped.")
            return
        self.running = False
        logger.info("Streamer running status is set to False. Waiting 5 seconds before stopping...")
        time.sleep(5)       # Waiting time for running tasks to complete
        if self.consumer:
            try:
                self.consumer.close()
                logger.info("Kafka consumer closed.")
            except Exception as e:
                logger.error(f"Error closing Kafka consumer: {e}")

        if self.client is not None and hasattr(self.client, 'status') and self.client.status == 'running':
            try:
                self.client.close()
                logger.info("Dask client closed.")
            except Exception as e:
                logger.error(f"Error closing Dask client: {e}")

# TODO: May be Single streamer for all analyzers ... ?
