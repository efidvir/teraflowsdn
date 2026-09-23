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

# Run AI Analytics Engine API tests
#
# Usage: ./run_test.sh

# Navigate to TFS root directory
cd "$(dirname "$0")"

# Set Python path to include TFS src and AI Analytics Engine
export PYTHONPATH="${PWD}/src:${PWD}/src/tests/tools/simap_ai_engine"

# Activate virtual environment if not already activated
# if [ -z "$VIRTUAL_ENV" ]; then
#     if [ -d "$HOME/.env-simap" ]; then
#         source "$HOME/.env-simap/bin/activate"
#     fi
# fi
echo "$PWD"
echo "Running AI Analytics Engine API tests..."

# Define log file path
LOG_FILE="${PWD}/test_api_docker.log"
TEST_FILE="${PWD}/test_api_docker.py"

# Run the test with logging enabled and capture output

pytest $TEST_FILE::test_stop_all_analyses_endpoint \
# pytest $TEST_FILE::test_analyze_endpoint \
    -v -s \
    --log-cli-level=DEBUG \
    --log-file="${LOG_FILE}" \
    --log-file-level=DEBUG \
    "$@"

echo ""
echo "Test logs saved to: ${LOG_FILE}"
