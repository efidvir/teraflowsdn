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


# -----------------------------------
# CONFIGURATION
# -----------------------------------

GRAFANA_URL="http://localhost:80/grafana"  # Your Grafana URL
GRAFANA_USERNAME="admin"
GRAFANA_PASSWORD="admin"

DATASOURCE_NAME="Prometheus"
DASHBOARD_FILE="/home/ubuntu/tfs-ctrl/src/tests/p4-sd-fabric-svc-connectivity/descriptors/grafana-latency.json" # Path to your dashboard JSON

# -----------------------------------
# READ DASHBOARD JSON
# -----------------------------------
if [ ! -f "$DASHBOARD_FILE" ]; then
    echo "[ERROR] Dashboard file not found: $DASHBOARD_FILE"
    exit 1
fi

DASHBOARD_JSON=$(cat "$DASHBOARD_FILE")

# ---------------------------------------
# 1. Get the datasource UID
# ---------------------------------------

PROM_UID=$(curl -s \
  -u "${GRAFANA_USERNAME}:${GRAFANA_PASSWORD}" \
  "${GRAFANA_URL}/api/datasources/name/${DATASOURCE_NAME}" \
  | jq -r '.uid')

if [ -z "$PROM_UID" ] || [ "$PROM_UID" == "null" ]; then
  echo "ERROR: Could not retrieve datasource UID. Check datasource name/auth."
  exit 1
fi

echo "Found datasource UID: $PROM_UID"

# ---------------------------------------
# 2. Inject the UID into dashboard JSON
# ---------------------------------------

DASHBOARD_JSON=$(jq --arg uid "$PROM_UID" '
  walk(
    if type == "object" and has("datasource") then
      .datasource |=
        (if type == "object" then .uid = $uid else $uid end)
    else .
    end
  )
' "$DASHBOARD_FILE")

# ---------------------------------------
# 3. Wrap in Grafana API import format
# ---------------------------------------

read -r -d '' IMPORT_JSON << EOF
{
  "dashboard": ${DASHBOARD_JSON},
  "overwrite": true,
  "folderId": 0,
  "message": "Imported via API"
}
EOF

# -----------------------------------
# 4. Import dashboard using API
# -----------------------------------

echo "Importing dashboard into Grafana..."

curl -X POST "${GRAFANA_URL}/api/dashboards/db" \
  -H "Content-Type: application/json" \
  -u "${GRAFANA_USERNAME}:${GRAFANA_PASSWORD}" \
  -d "${IMPORT_JSON}"

echo
echo "Done"
