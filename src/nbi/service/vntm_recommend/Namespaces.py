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

import json, logging
from flask import request
from flask_socketio import Namespace, join_room, leave_room
from kafka import KafkaProducer
from common.tools.kafka.Variables import KafkaConfig, KafkaTopic
from .Constants import SIO_NAMESPACE, SIO_ROOM
from .VntRecommThread import VntRecommThread

LOGGER = logging.getLogger(__name__)

class VntRecommServerNamespace(Namespace):
    def __init__(self):
        super().__init__(namespace=SIO_NAMESPACE)
        self._thread = VntRecommThread(self)
        self._thread.start()

        self.kafka_producer = KafkaProducer(
            bootstrap_servers = KafkaConfig.get_kafka_address(),
        )

    def stop_thread(self) -> None:
        self._thread.stop()

    def on_connect(self, auth):
        MSG = '[on_connect] Client connect: sid={:s}, auth={:s}'
        LOGGER.debug(MSG.format(str(request.sid), str(auth)))
        join_room(SIO_ROOM, namespace=SIO_NAMESPACE)

    def on_disconnect(self, reason):
        MSG = '[on_disconnect] Client disconnect: sid={:s}, reason={:s}'
        LOGGER.debug(MSG.format(str(request.sid), str(reason)))
        leave_room(SIO_ROOM, namespace=SIO_NAMESPACE)

    @staticmethod
    def _parse_payload(data):
        if isinstance(data, str):
            return json.loads(data)
        if isinstance(data, dict):
            return dict(data)
        raise TypeError('Unsupported recommendation callback payload type: {:s}'.format(type(data).__name__))

    def _publish_reply(self, event_name: str, data) -> None:
        sid = getattr(request, 'sid', '<unknown>')
        LOGGER.info('[%s] begin: sid=%s payload=%s', event_name, sid, str(data))

        json_data = self._parse_payload(data)
        request_key = str(json_data.pop('_request_key')).encode('utf-8')
        vntm_reply = json.dumps({'event': event_name, 'data': json_data}).encode('utf-8')

        LOGGER.info(
            '[%s] Publishing Kafka reply: request_key=%s payload=%s',
            event_name, request_key.decode('utf-8'), vntm_reply.decode('utf-8')
        )
        self.kafka_producer.send(
            KafkaTopic.VNTMANAGER_RESPONSE.value, key=request_key, value=vntm_reply
        )
        self.kafka_producer.flush()
        LOGGER.info('[%s] Kafka reply published', event_name)

    def on_vlink_created(self, data):
        try:
            self._publish_reply('vlink_created', data)
        except Exception:
            LOGGER.exception('[on_vlink_created] Failed to process callback')
            raise

    def on_vlink_removed(self, data):
        try:
            self._publish_reply('vlink_removed', data)
        except Exception:
            LOGGER.exception('[on_vlink_removed] Failed to process callback')
            raise
