#!/bin/bash
# Copyright 2022-2026 ETSI SDG TeraFlowSDN (TFS) (https://tfs.etsi.org/)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


# ---------------------------
# CONFIGURATION
# ---------------------------

TFS_IP="192.168.5.137"

GRAFANA_URL="http://localhost:80/grafana"  # Your Grafana URL
GRAFANA_USERNAME="admin"
GRAFANA_PASSWORD="admin"

DATASOURCE_NAME="Prometheus"
PROMETHEUS_URL="http://${TFS_IP}:30090/"   # URL of your Prometheus server

# ---------------------------
# CREATE DATA SOURCE PAYLOAD
# ---------------------------

read -r -d '' DATA_SOURCE_JSON << EOF
{
  "name": "${DATASOURCE_NAME}",
  "type": "prometheus",
  "access": "proxy",
  "url": "${PROMETHEUS_URL}",
  "basicAuth": false,
  "isDefault": true,
  "editable": true
}
EOF

# ---------------------------
# SEND REQUEST (with username/password)
# ---------------------------

echo "Creating Prometheus datasource in Grafana..."

curl -X POST "${GRAFANA_URL}/api/datasources" \
  -H "Content-Type: application/json" \
  -u "${GRAFANA_USERNAME}:${GRAFANA_PASSWORD}" \
  -d "${DATA_SOURCE_JSON}"

echo
echo "Done"
