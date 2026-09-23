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

# Set working directory
cd "$(dirname "$0")" || exit 1

# Assuming the instances are named as: simap-datastore, tfs-e2e-ctrl, tfs-agg-ctrl, tfs-ip-ctrl

# Get the current hostname
HOSTNAME=$(hostname)
echo "Collecting logs for ${HOSTNAME}..."

rm logs -rf tmp/exec
mkdir -p tmp/exec

case "$HOSTNAME" in
    simap-datastore)
        echo "Collecting Docker container logs..."
        docker logs simap-datastore > tmp/exec/simap-datastore.log 2>&1
        docker logs nce-fan-ctrl    > tmp/exec/nce-fan-ctrl.log 2>&1
        docker logs nce-t-ctrl      > tmp/exec/nce-t-ctrl.log 2>&1
        docker logs traffic-changer > tmp/exec/traffic-changer.log 2>&1
        ;;
    tfs-e2e-ctrl)
        echo "Collecting TFS E2E Controller logs..."
        kubectl logs --namespace tfs service/contextservice          -c server   > tmp/exec/e2e-context.log
        kubectl logs --namespace tfs service/deviceservice           -c server   > tmp/exec/e2e-device.log
        kubectl logs --namespace tfs service/serviceservice          -c server   > tmp/exec/e2e-service.log
        kubectl logs --namespace tfs service/pathcompservice         -c frontend > tmp/exec/e2e-pathcomp-frontend.log
        kubectl logs --namespace tfs service/pathcompservice         -c backend  > tmp/exec/e2e-pathcomp-backend.log
        kubectl logs --namespace tfs service/webuiservice            -c server   > tmp/exec/e2e-webui.log
        kubectl logs --namespace tfs service/nbiservice              -c server   > tmp/exec/e2e-nbi.log
        kubectl logs --namespace tfs service/simap-connectorservice  -c server   > tmp/exec/e2e-simap-connector.log
        ;;
    tfs-agg-ctrl)
        echo "Collecting TFS Aggregation Controller logs..."
        kubectl logs --namespace tfs service/contextservice          -c server   > tmp/exec/agg-context.log
        kubectl logs --namespace tfs service/deviceservice           -c server   > tmp/exec/agg-device.log
        kubectl logs --namespace tfs service/serviceservice          -c server   > tmp/exec/agg-service.log
        kubectl logs --namespace tfs service/pathcompservice         -c frontend > tmp/exec/agg-pathcomp-frontend.log
        kubectl logs --namespace tfs service/pathcompservice         -c backend  > tmp/exec/agg-pathcomp-backend.log
        kubectl logs --namespace tfs service/webuiservice            -c server   > tmp/exec/agg-webui.log
        kubectl logs --namespace tfs service/nbiservice              -c server   > tmp/exec/agg-nbi.log
        kubectl logs --namespace tfs service/simap-connectorservice  -c server   > tmp/exec/agg-simap-connector.log
        ;;
    tfs-ip-ctrl)
        echo "Collecting TFS IP Controller logs..."
        kubectl logs --namespace tfs service/contextservice          -c server   > tmp/exec/ip-context.log
        kubectl logs --namespace tfs service/deviceservice           -c server   > tmp/exec/ip-device.log
        kubectl logs --namespace tfs service/serviceservice          -c server   > tmp/exec/ip-service.log
        kubectl logs --namespace tfs service/pathcompservice         -c frontend > tmp/exec/ip-pathcomp-frontend.log
        kubectl logs --namespace tfs service/pathcompservice         -c backend  > tmp/exec/ip-pathcomp-backend.log
        kubectl logs --namespace tfs service/webuiservice            -c server   > tmp/exec/ip-webui.log
        kubectl logs --namespace tfs service/nbiservice              -c server   > tmp/exec/ip-nbi.log
        kubectl logs --namespace tfs service/simap-connectorservice  -c server   > tmp/exec/ip-simap-connector.log
        ;;
    *)
        echo "Unknown host: $HOSTNAME"
        echo "No logs to collect."
        ;;
esac

printf "\n"

echo "Done!"
