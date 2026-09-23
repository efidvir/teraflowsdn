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

# SIMAP Connector Integration Tests
#
# This test does NOT require:
# - TFS Context service
# - SIMAP server
# - Any external services
#
# Uses in-memory context store and mock HTTP server.

PROJECTDIR=`pwd`

cd $PROJECTDIR/src

export PYTHONPATH=$PROJECTDIR/src:$PROJECTDIR/src/tests/tools/simap_ai_engine

# Run the mocked integration test (no external dependencies)
python3 -m pytest --verbose \
    --log-cli-level=DEBUG -v -s \
    tests/tools/simap_ai_engine/ai_engine/tests/test_api.py
