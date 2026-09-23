#!/bin/bash
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


# Cleanup
docker rm --force simap-datastore


# Create SIMAP Datastore with InfluxDB configuration
# INFLUXDB_HOST points to the host machine where InfluxDB is running
# Use --add-host to make the host accessible from inside the container
docker run --detach --name simap-datastore \
    --publish 8080:8080 \
    --add-host=host.docker.internal:host-gateway \
    --env INFLUXDB_HOST="host.docker.internal" \
    --env INFLUXDB_PORT=8181 \
    --env INFLUXDB_DATABASE=simap_telemetry \
    simap-datastore:test


sleep 2


# Dump SIMAP Datastore container
docker ps -a


echo "Bye!"
