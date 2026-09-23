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

"""
Test suite for AI Engine REST API.

This module tests the /api/v1/analyze endpoint by starting the server
and sending HTTP requests.
"""

import logging
import os
import sys
import threading
import time

import pytest
import requests

# Add TFS src directory and AI Engine package root to path.
# Must be done before any package imports.
current_dir = os.path.dirname(os.path.abspath(__file__))
tfs_src_dir = os.path.abspath(os.path.join(current_dir, '../../../../..'))
ai_engine_root_dir = os.path.abspath(os.path.join(current_dir, '../..'))
if tfs_src_dir not in sys.path:
    sys.path.insert(0, tfs_src_dir)
if ai_engine_root_dir not in sys.path:
    sys.path.insert(0, ai_engine_root_dir)

# Now we can import from the AI Engine package
from ai_engine import AIEngineAPI

# Configure logging for tests
logging.basicConfig(
    level=logging.DEBUG,
    format="[%(asctime)s] %(levelname)s:%(name)s:%(message)s"
)
LOGGER = logging.getLogger(__name__)

# Test server configuration
TEST_HOST = '127.0.0.1'
TEST_PORT = 8085  # 18080 port for manual testing

BASE_URL = f'http://{TEST_HOST}:{TEST_PORT}'


@pytest.fixture(scope='module')
def ai_engine_server():
    """
    Fixture to start the AI Analytics Engine server in a background thread.
    
    Yields control to tests once server is ready, then performs cleanup.
    """
    LOGGER.info("Starting AI Analytics Engine server fixture")
    
    # Override config for testing
    os.environ['AI_ENGINE_REST_HOST'] = TEST_HOST
    os.environ['AI_ENGINE_REST_PORT'] = str(TEST_PORT)
    
    # Create engine instance
    engine = AIEngineAPI()
    
    # Start server in background thread
    server_thread = threading.Thread(
        target=lambda: engine.app.run(
            host=TEST_HOST,
            port=TEST_PORT,
            debug=False,
            use_reloader=False
        ),
        daemon=True
    )
    server_thread.start()
    
    # Wait for server to be ready
    max_retries = 15
    for i in range(max_retries):
        try:
            LOGGER.debug(f"Waiting for server to start... ({i+1}/{max_retries})")
            response = requests.get(f'{BASE_URL}/api/v1/config', timeout=1)
            if response.status_code == 200:
                LOGGER.info("AI Analytics Engine server is ready")
                break
        except requests.exceptions.RequestException as e:
            # LOGGER.debug(f"Server not ready yet: {e}")
            if i < max_retries - 1:
                time.sleep(5)
            else:
                raise RuntimeError("Failed to start AI Analytics Engine server")
    
    yield engine
    
    LOGGER.info("AI Analytics Engine server fixture cleanup complete")



def test_analyze_endpoint(ai_engine_server):
    """
    Test POST /api/v1/analyze endpoint.

    Validates that the analyze endpoint:
    - Accepts valid SLA policy JSON payload
    - Returns appropriate status codes (200 for success, 503 for service unavailable)
    - Returns JSON response with status and message fields
    """

    LOGGER.info(">>>>>> Starting test_case test_analyze_endpoint: POST /api/v1/analyze endpoint")
    
    # Prepare test payload with SLA policy configuration
    payload = {
        "simap_id": "E2E-L1",
        "sla_metrics": {
            "latency_threshold_ms": 0,
            "bandwidth_utilization": 0.0
        },
        "history_window_size_sec":      600,
        "forecast_sample_interval_sec": 5,
        "forecast_sample_count":        120,
    }

    LOGGER.info(f"Sending analyze request with payload: {payload}")
    
    # Send POST request to analyze endpoint
    response = requests.post(
        f'{BASE_URL}/api/v1/analyze',
        json=payload,
        timeout=10
    )

    # Add condition to validate response status code and content
    
    LOGGER.info(f"Analyze response status: {response.status_code}")
    
    # Parse JSON response
    data = response.json()
    LOGGER.info(f"Analyze response body: {data}")
    
    # Validate response structure
    assert 'status' in data, "Response missing 'status' field"
    assert 'message' in data, "Response missing 'message' field"
    
    # Accept either success (200) or service unavailable (503)
    # 503 is expected if SIMAP server or InfluxDB are not running
    if response.status_code == 200:
        LOGGER.info("Analysis completed successfully")
        assert data['status'] == 'success', f"Expected status 'success', got '{data['status']}'"
        assert 'data' in data, "Successful response missing 'data' field"
    elif response.status_code == 503:
        # LOGGER.error("External service unavailable (expected if SIMAP/InfluxDB not running)")
        assert data['status'] == 'error', f"Expected status 'error' for 503, got '{data['status']}'"
        pytest.fail("External service unavailable (expected if SIMAP/InfluxDB not running)")
    elif response.status_code == 400:
        LOGGER.error(f"Bad request: {data['message']}")
        assert data['status'] == 'error', f"Expected status 'error' for 400, got '{data['status']}'"
        pytest.fail(f"Bad request: {data['message']}")
    else:
        pytest.fail(f"Unexpected status code: {response.status_code}")
    
    LOGGER.info("Analyze endpoint test passed!")
    LOGGER.info("<<<<<< Finished test_case test_analyze_endpoint")


def test_notify_endpoint():
    """
    Test POST /api/v1/notify endpoint with valid status-only payload.

    Validates that the notify endpoint:
    - Accepts valid notification payload with only "status" key
    - Returns appropriate status codes (200 for success, 503 for service unavailable)
    - Returns JSON response with status and message fields
    """
    LOGGER.info(">>>>>> Starting test_case test_notify_endpoint: POST /api/v1/notify endpoint")
    
    payload = {"status": "UPGRADE"}
    LOGGER.info(f"Sending notify request with payload: {payload}")

    # Send POST request to notify endpoint
    response = requests.post(
        f'{BASE_URL}/api/v1/notify',
        json=payload,
        timeout=10
    )

    LOGGER.info(f"Notify response status: {response.status_code}")

    # Parse JSON response
    data = response.json()
    LOGGER.info(f"Notify response body: {data}")
    
    # Validate response structure
    assert 'status' in data, "Response missing 'status' field"
    assert 'message' in data, "Response missing 'message' field"
    
    # Accept either success (200) or service unavailable (503)
    # 503 is expected if InfluxDB is not running
    if response.status_code == 200:
        LOGGER.info("Notification processed successfully")
        assert data['status'] == 'success', f"Expected status 'success', got '{data['status']}'"
    elif response.status_code == 503:
        LOGGER.warning("InfluxDB unavailable (expected if InfluxDB not running)")
        assert data['status'] == 'error', f"Expected status 'error' for 503, got '{data['status']}'"
    else:
        pytest.fail(f"Unexpected status code: {response.status_code}")
    
    LOGGER.info("Notify endpoint test passed!")
    LOGGER.info("<<<<<< Finished test_case test_notify_endpoint")
