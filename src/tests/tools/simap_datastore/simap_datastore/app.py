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


# This file overwrites default RestConf Server `app.py` file.


import logging
from common.tools.rest_conf.server.restconf_server.RestConfServerApplication import RestConfServerApplication
from .TelemetryCallbacks import CallbackOnLinkTelemetry, CallbackOnNodeTelemetry
from .Config import INFLUXDB_HOST, INFLUXDB_PORT, INFLUXDB_TOKEN, INFLUXDB_DATABASE
from .influxdb_client import SimapInfluxDBClient


logging.basicConfig(
    level  = logging.INFO,
    format = '[Worker-%(process)d][%(asctime)s] %(levelname)s:%(name)s:%(message)s',
)
LOGGER = logging.getLogger(__name__)

LOGGER.info('Starting...')
rcs_app = RestConfServerApplication()
rcs_app.register_host_meta()
rcs_app.register_restconf()
LOGGER.info('All connectors registered')

# Initialize InfluxDB client and register telemetry callbacks
try:
    LOGGER.info('Initializing InfluxDB client (host=%s, port=%d, db=%s)...', INFLUXDB_HOST, INFLUXDB_PORT, INFLUXDB_DATABASE)
    influx_client = SimapInfluxDBClient(
        host     = INFLUXDB_HOST,
        port     = INFLUXDB_PORT,
        token    = INFLUXDB_TOKEN,
        database = INFLUXDB_DATABASE
    )
except Exception as e:
    LOGGER.error('Failed to initialize InfluxDB client: %s', e)
    influx_client = None

if influx_client is not None and influx_client.is_connected():
    try:
        rcs_app.callback_dispatcher.register(CallbackOnLinkTelemetry(influx_client))
        rcs_app.callback_dispatcher.register(CallbackOnNodeTelemetry(influx_client))
        LOGGER.info('Telemetry callbacks registered')
    except Exception as e:
        LOGGER.error('Failed to register telemetry callbacks: %s', e)
else:
    LOGGER.warning('InfluxDB client not connected, telemetry callbacks disabled.')

rcs_app.dump_configuration()
app = rcs_app.get_flask_app()

LOGGER.info('Initialization completed!')
