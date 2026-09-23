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

# Get the current hostname
HOSTNAME=$(hostname)
echo "Starting telemetry subscription for ${HOSTNAME}..."

case "$HOSTNAME" in
    tfs-e2e-ctrl)
        echo "Subscribing to E2E Controller telemetry..."
        python3 telemetry-subscribe-slice1.py e2e E2E-L1
        ;;
    tfs-agg-ctrl)
        echo "Subscribing to Aggregation Controller telemetry..."
        python3 telemetry-subscribe-slice1.py agg AggNet-L1
        ;;
    tfs-ip-ctrl)
        echo "Subscribing to IP Controller telemetry..."
        python3 telemetry-subscribe-slice1.py trans-pkt Trans-L1
        ;;
    *)
        echo "Unknown host: $HOSTNAME"
        echo "Usage: $0"
        echo "  This script must be run on tfs-e2e-ctrl, tfs-agg-ctrl, or tfs-ip-ctrl"
        exit 1
        ;;
esac
