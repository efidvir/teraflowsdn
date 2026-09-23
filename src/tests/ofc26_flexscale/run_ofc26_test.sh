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

# Make folder containing the script the root folder for its execution
cd $(dirname $0)/../../../
echo "Running OFC26 test from folder: $(pwd)"
cd src/
CRDB_SQL_ADDRESS=$(kubectl get service --namespace ${CRDB_NAMESPACE} cockroachdb-public -o 'jsonpath={.spec.clusterIP}')
export CRDB_URI="cockroachdb://tfs:tfs123@${CRDB_SQL_ADDRESS}:26257/tfs_kpi_mgmt?sslmode=require"

#added for kafka exposure
export KFK_SERVER_ADDRESS='127.0.0.1:9092'

kubectl port-forward -n kafka service/kafka-service 9092:9092 > /dev/null 2>&1 &
KAFKA_PF_PID=$!

# Function to cleanup port-forward on exit
cleanup() {
    # echo "Cleaning up Kafka port-forward (PID: ${KAFKA_PF_PID})..."
    kill ${KAFKA_PF_PID} 2>/dev/null || true
    wait ${KAFKA_PF_PID} 2>/dev/null || true
}


IP_KPI=$(kubectl get all --all-namespaces | grep service/kpi-managerservice | awk '{print $4}')
export IP_KPI
echo "KPI Manager Service IP: ${IP_KPI}"

IP_TELE=$(kubectl get all --all-namespaces | grep service/telemetryservice | awk '{print $4}')
export IP_TELE
echo "Telemetry Frontend Service IP: ${IP_TELE}"


python -m pytest --log-level=INFO --log-cli-level=INFO --verbose \
    tests/ofc26_flexscale/test_ofc26_mgon_integration_V2.py
