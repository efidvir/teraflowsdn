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

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../../.." && pwd)"

docker rm --force ai-engine 2>/dev/null || true

echo "Building AI Engine..."
cd "${REPO_ROOT}"
docker buildx build -t ai-engine:latest -f ./src/tests/tools/simap_ai_engine/ai_engine/Dockerfile .

echo "Deploying AI Engine..."
docker run --detach --name ai-engine \
  --publish 8084:8080 \
  --env SIMAP_DATASTORE_ADDRESS=172.17.0.1 \
  --env SIMAP_DATASTORE_PORT=8080 \
  --env SIMAP_DATASTORE_USERNAME=admin \
  --env SIMAP_DATASTORE_PASSWORD=admin \
  ai-engine:latest
# docker run --detach --name traffic-changer --publish 8083:8080 traffic-changer:mock

sleep 2
docker ps -a
echo "Deployment complete."
