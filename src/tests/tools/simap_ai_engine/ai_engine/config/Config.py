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

"""
Configuration module for the AI Engine.

This module defines environment variables for SIMAP server, InfluxDB,
and REST API configuration using the TFS get_setting pattern.
"""

from common.Settings import get_setting

# SIMAP Datastore Configuration
SIMAP_DATASTORE_SCHEME   = get_setting('SIMAP_DATASTORE_SCHEME',   default='http')
SIMAP_DATASTORE_ADDRESS  = get_setting('SIMAP_DATASTORE_ADDRESS',  default='0.0.0.0')
SIMAP_DATASTORE_PORT     = int(get_setting('SIMAP_DATASTORE_PORT', default='80'))
SIMAP_DATASTORE_USERNAME = get_setting('SIMAP_DATASTORE_USERNAME', default='admin')
SIMAP_DATASTORE_PASSWORD = get_setting('SIMAP_DATASTORE_PASSWORD', default='admin')

# InfluxDB Configuration
INFLUXDB_HOST     = get_setting('INFLUXDB_HOST',     default='localhost')
INFLUXDB_PORT     = int(get_setting('INFLUXDB_PORT', default='8181'))
INFLUXDB_TOKEN    = get_setting('INFLUXDB_TOKEN',    default='')
INFLUXDB_DATABASE = get_setting('INFLUXDB_DATABASE', default='simap_telemetry')

# AI Engine REST API Configuration
AI_ENGINE_REST_HOST = get_setting('AI_ENGINE_REST_HOST',     default='0.0.0.0')
AI_ENGINE_REST_PORT = int(get_setting('AI_ENGINE_REST_PORT', default='8080'))
