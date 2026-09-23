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

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TMP_LOG_PATH="$SCRIPT_DIR/tmp/exec"

echo "Cleaning old logs from $TMP_LOG_PATH"
rm -rf $TMP_LOG_PATH

echo "Dumping logs to $TMP_LOG_PATH"
mkdir -p $TMP_LOG_PATH
cd $TMP_LOG_PATH

echo "Collecting logs for E2E..."
kubectl logs --namespace tfs-e2e deployment/contextservice          -c server   > e2e-context.log
kubectl logs --namespace tfs-e2e deployment/deviceservice           -c server   > e2e-device.log
kubectl logs --namespace tfs-e2e deployment/serviceservice          -c server   > e2e-service.log
kubectl logs --namespace tfs-e2e deployment/pathcompservice         -c frontend > e2e-pathcomp-frontend.log
kubectl logs --namespace tfs-e2e deployment/pathcompservice         -c backend  > e2e-pathcomp-backend.log
kubectl logs --namespace tfs-e2e deployment/webuiservice            -c server   > e2e-webui.log
kubectl logs --namespace tfs-e2e deployment/nbiservice              -c server   > e2e-nbi.log
kubectl logs --namespace tfs-e2e deployment/e2e-orchestratorservice -c server   > e2e-orch.log
printf "\n"

echo "Collecting logs for IP..."
kubectl logs --namespace tfs-ip deployment/contextservice     -c server   > ip-context.log
kubectl logs --namespace tfs-ip deployment/deviceservice      -c server   > ip-device.log
kubectl logs --namespace tfs-ip deployment/serviceservice     -c server   > ip-service.log
kubectl logs --namespace tfs-ip deployment/pathcompservice    -c frontend > ip-pathcomp-frontend.log
kubectl logs --namespace tfs-ip deployment/pathcompservice    -c backend  > ip-pathcomp-backend.log
kubectl logs --namespace tfs-ip deployment/webuiservice       -c server   > ip-webui.log
kubectl logs --namespace tfs-ip deployment/nbiservice         -c server   > ip-nbi.log
kubectl logs --namespace tfs-ip deployment/vnt-managerservice -c server   > ip-vntm.log
printf "\n"

echo "Collecting logs for OPT..."
kubectl logs --namespace tfs-opt deployment/contextservice           -c server   > opt-context.log
kubectl logs --namespace tfs-opt deployment/deviceservice            -c server   > opt-device.log
kubectl logs --namespace tfs-opt deployment/serviceservice           -c server   > opt-service.log
kubectl logs --namespace tfs-opt deployment/pathcompservice          -c frontend > opt-pathcomp-frontend.log
kubectl logs --namespace tfs-opt deployment/pathcompservice          -c backend  > opt-pathcomp-backend.log
kubectl logs --namespace tfs-opt deployment/webuiservice             -c server   > opt-webui.log
kubectl logs --namespace tfs-opt deployment/nbiservice               -c server   > opt-nbi.log
kubectl logs --namespace tfs-opt deployment/opticalcontrollerservice -c server   > opt-ctrl.log
printf "\n"

echo "Done!"
