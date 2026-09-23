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


PROJECTDIR=`pwd`

cd $PROJECTDIR/src
# RCFILE=$PROJECTDIR/coverage/.coveragerc

CRDB_SQL_ADDRESS=$(kubectl get service cockroachdb-public --namespace crdb -o jsonpath='{.spec.clusterIP}')
export CRDB_URI="cockroachdb://tfs:tfs123@${CRDB_SQL_ADDRESS}:26257/tfs_telemetry?sslmode=require"
# RCFILE=$PROJECTDIR/coverage/.coveragerc

export KFK_SERVER_ADDRESS='127.0.0.1:9094'

IP_KPI=$(kubectl get all --all-namespaces | grep service/kpi-managerservice | awk '{print $4}')
export IP_KPI
echo "KPI Manager Service IP: ${IP_KPI}"

IP_TELE=$(kubectl get all --all-namespaces | grep service/telemetryservice | awk '{print $4}')
export IP_TELE
echo "Telemetry Frontend Service IP: ${IP_TELE}"

IP_CONTEXT=$(kubectl get all --all-namespaces | grep service/contextservice | awk '{print $4}')
export IP_CONTEXT
echo "Context Service IP: ${IP_CONTEXT}"

# Start Kafka port-forward in background
kubectl port-forward -n kafka service/kafka-service 9094:9094 > /dev/null 2>&1 &
KAFKA_PF_PID=$!

# Function to cleanup port-forward on exit
cleanup() {
    # echo "Cleaning up Kafka port-forward (PID: ${KAFKA_PF_PID})..."
    kill ${KAFKA_PF_PID} 2>/dev/null || true
    wait ${KAFKA_PF_PID} 2>/dev/null || true
    sleep 1
}

trap cleanup EXIT INT TERM
echo "Waiting for Kafka port-forward to be ready..."
sleep 1

# Verify port-forward is working
if ! nc -z 127.0.0.1 9094 2>/dev/null; then
    echo "WARNING: Kafka port-forward may not be ready yet"
fi

python3 -m pytest --log-level=INFO --log-cli-level=INFO --verbose \
    telemetry/backend/tests/test_backend.py
