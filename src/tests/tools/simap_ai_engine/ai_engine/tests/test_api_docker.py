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
Test suite for AI Analytics Engine REST API running in Docker.

This module tests the /api/v1/analyze endpoint by connecting to the
AI-Engine Docker container exposed on port 8084.
"""

import logging
import time

import pytest
import requests

# Configure logging for tests
logging.basicConfig(
    level=logging.DEBUG,
    format="[%(asctime)s] %(levelname)s:%(name)s:%(message)s"
)
LOGGER = logging.getLogger(__name__)

# Test server configuration - Docker container exposed port
TEST_HOST = '127.0.0.1'
TEST_PORT = 8084  # Docker container port mapping: 8084->8080

BASE_URL = f'http://{TEST_HOST}:{TEST_PORT}'



@pytest.fixture(scope='module')
def ai_engine_server_connection_confirmation():
    """
    Fixture to verify the AI Analytics Engine Docker container is running.
    
    Checks connectivity to the Docker container and yields control to tests.
    Assumes the container is already running (docker run -p 8084:8080 ai-engine:latest).
    """
    LOGGER.info("Checking AI Analytics Engine Docker container availability")
    
    # Wait for server to be ready
    max_retries = 15
    for i in range(max_retries):
        try:
            LOGGER.debug(f"Checking Docker container connectivity... ({i+1}/{max_retries})")
            response = requests.get(f'{BASE_URL}/api/v1/config', timeout=2)
            if response.status_code == 200:
                LOGGER.info("AI Analytics Engine Docker container is ready")
                break
        except requests.exceptions.RequestException as e:
            LOGGER.debug(f"Container not ready yet: {e}")
            if i < max_retries - 1:
                time.sleep(2)
            else:
                raise RuntimeError(
                    f"Failed to connect to AI Analytics Engine Docker container at {BASE_URL}. "
                    f"Ensure container is running: docker run -p 8084:8080 ai-engine:latest"
                )
    
    yield
    
    LOGGER.info("AI Analytics Engine Docker test fixture cleanup complete")



def test_analyze_endpoint(ai_engine_server_connection_confirmation):
    """
    Test POST /api/v1/analyze endpoint.

    Validates that the analyze endpoint:
    - Accepts valid SLA policy JSON payload
    - Returns 202 Accepted for background processing
    - Returns JSON response with status, message, simap_id, duration, and endpoint fields
    """

    LOGGER.info(">>>>>> Starting test_case test_analyze_endpoint: POST /api/v1/analyze endpoint")
    
    # Prepare test payload with SLA policy configuration
    payload = {
        "simap_id": "E2E-L1",
        "sla_metrics": {
            "latency_threshold_ms":  0,
            "bandwidth_utilization": 0.0
        },
        "history_window_size_sec":      60,
        "forecast_sample_interval_sec": 30,
        "forecast_sample_count":        50,
        "duration_minutes":             10  # Short duration for testing
    }

    LOGGER.info(f"Sending analyze request with payload: {payload}")
    
    # Send POST request to analyze endpoint
    response = requests.post(
        f'{BASE_URL}/api/v1/analyze',
        json=payload,
        timeout=10
    )
    
    LOGGER.info(f"Analyze response status: {response.status_code}")
    
    # Parse JSON response
    data = response.json()
    LOGGER.info(f"Analyze response body: {data}")
    
    # Validate response structure
    assert 'status' in data, "Response missing 'status' field"
    assert 'message' in data, "Response missing 'message' field"
    
    # Accept either accepted (202) or service unavailable (503)
    # 503 is expected if SIMAP server or InfluxDB are not running
    if response.status_code == 202:
        LOGGER.info("Analysis started successfully")
        assert data['status']             ==  'accepted',       f"Expected status 'accepted',         got '{data['status']}'"
        assert data['simap_id']           ==  'E2E-L1',         f"Expected simap_id 'E2E-L1',         got '{data['simap_id']}'"
        assert data['duration_minutes']   ==  2,                f"Expected duration_minutes 2,        got '{data['duration_minutes']}'"
        assert '/osm/aiAnalyticsEvent/v1' in  data['endpoint'], f"Expected '/osm/aiAnalyticsEvent/v1' in  endpoint"
    elif response.status_code == 503:
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


def test_status_endpoint(ai_engine_server):
    """
    Test GET /api/v1/status endpoint.

    Validates that the status endpoint:
    - Returns list of running analyses
    - Includes running_count, analyses array, and timestamp
    - Each analysis has simap_id, is_alive, start_time, duration_minutes
    """

    LOGGER.info(">>>>>> Starting test_case test_status_endpoint: GET /api/v1/status endpoint")
    
    # Send GET request to status endpoint
    response = requests.get(
        f'{BASE_URL}/api/v1/status',
        timeout=5
    )
    
    LOGGER.info(f"Status response status: {response.status_code}")
    assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"
    
    # Parse JSON response
    data = response.json()
    LOGGER.info(f"Status response body: {data}")
    
    # Validate response structure
    assert 'running_count' in data, "Response missing 'running_count' field"
    assert 'analyses'      in data, "Response missing 'analyses' field"
    assert 'timestamp'     in data, "Response missing 'timestamp' field"
    assert isinstance(data['analyses'], list), "Field 'analyses' should be a list"
    
    # If there are running analyses, validate their structure
    if data['running_count'] > 0:
        LOGGER.info(f"Found {data['running_count']} running analyses")
        for analysis in data['analyses']:
            assert 'simap_id'         in analysis, "Analysis missing 'simap_id' field"
            assert 'is_alive'         in analysis, "Analysis missing 'is_alive' field"
            assert 'start_time'       in analysis, "Analysis missing 'start_time' field"
            assert 'duration_minutes' in analysis, "Analysis missing 'duration_minutes' field"
    else:
        LOGGER.info("No analyses currently running")
    
    LOGGER.info("Status endpoint test passed!")
    LOGGER.info("<<<<<< Finished test_case test_status_endpoint")


def test_stop_analyze_endpoint(ai_engine_server):
    """
    Test POST /api/v1/analyze/stop endpoint.

    Validates that the stop endpoint:
    - Stops a running analysis by simap_id
    - Returns 404 if no analysis found
    - Returns 200 on successful stop
    """

    LOGGER.info(">>>>>> Starting test_case test_stop_analyze_endpoint: POST /api/v1/analyze/stop endpoint")
    
    # First, start an analysis to test stopping it
    start_payload = {
        "simap_id": "L2",
        "sla_metrics": {
            "latency_threshold_ms":     0,
            "bandwidth_utilization":    0.0
        },
        "history_window_size_sec":      60,
        "forecast_sample_interval_sec": 5,
        "forecast_sample_count":        50,
        "duration_minutes":             5  # Longer duration so we can stop it
    }
    
    LOGGER.info(f"Starting analysis with payload: {start_payload}")
    start_response = requests.post(
        f'{BASE_URL}/api/v1/analyze',
        json=start_payload,
        timeout=10
    )
    
    # Only proceed with stop test if start was successful
    if start_response.status_code == 202:
        LOGGER.info("Analysis started, now testing stop endpoint")
        
        # Wait a moment to ensure thread is running
        time.sleep(2)
        
        # Test stopping the analysis
        stop_payload = {"simap_id": start_payload["simap_id"]}
        
        LOGGER.info(f"Sending stop request with payload: {stop_payload}")
        response = requests.post(
            f'{BASE_URL}/api/v1/analyze/stop',
            json=stop_payload,
            timeout=10
        )
        
        LOGGER.info(f"Stop response status: {response.status_code}")
        
        # Parse JSON response
        data = response.json()
        LOGGER.info(f"Stop response body: {data}")
        
        assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"
        assert data['status'] == 'success', f"Expected status 'success', got '{data['status']}'"
        assert data['simap_id'] == start_payload["simap_id"], f"Expected simap_id '{start_payload['simap_id']}', got '{data['simap_id']}'"
        
        LOGGER.info("Stop successful, verifying analysis is stopped")
        
        # Verify the analysis is no longer running
        time.sleep(1)
        status_response = requests.get(f'{BASE_URL}/api/v1/status', timeout=5)
        status_data = status_response.json()
        
        # Check if L1 is still in the list
        running_ids = [a['simap_id'] for a in status_data['analyses'] if a['is_alive']]
        assert 'L2' not in running_ids, "Analysis should be stopped"
        
        LOGGER.info("Verified analysis was stopped")
    else:
        LOGGER.warning(f"Skipping stop test - could not start analysis (status {start_response.status_code})")
        pytest.skip("Could not start analysis to test stop functionality")
    
    # Test stopping non-existent analysis
    LOGGER.info("Testing stop on non-existent analysis")
    stop_nonexistent = {"simap_id": "nonexistent-id"}
    response = requests.post(
        f'{BASE_URL}/api/v1/analyze/stop',
        json=stop_nonexistent,
        timeout=10
    )
    
    LOGGER.info(f"Stop nonexistent response status: {response.status_code}")
    data = response.json()
    LOGGER.info(f"Stop nonexistent response body: {data}")
    
    assert response.status_code == 404, f"Expected status code 404 for nonexistent, got {response.status_code}"
    assert data['status'] == 'error', f"Expected status 'error', got '{data['status']}'"
    
    LOGGER.info("Stop endpoint test passed!")
    LOGGER.info("<<<<<< Finished test_case test_stop_analyze_endpoint")


def test_stop_all_analyses_endpoint(ai_engine_server):
    """
    Test POST /api/v1/analyze/stop-all endpoint.

    Validates that the stop-all endpoint:
    - Stops all running analyses
    - Returns summary with stopped_count and stopped_ids
    - Handles case when no analyses are running
    """

    LOGGER.info(">>>>>> Starting test_case test_stop_all_analyses_endpoint: POST /api/v1/analyze/stop-all endpoint")
    started_ids = ["E2E-L1"]

    
    # Only proceed if at least one analysis started
    if len(started_ids) > 0:
        LOGGER.info(f"Started {len(started_ids)} analyses, now testing stop-all endpoint")
        
        # Call stop-all endpoint
        LOGGER.info("Sending stop-all request")
        response = requests.post(
            f'{BASE_URL}/api/v1/analyze/stop-all',
            timeout=10
        )
        
        LOGGER.info(f"Stop-all response status: {response.status_code}")
        
        # Parse JSON response
        data = response.json()
        LOGGER.info(f"Stop-all response body: {data}")
        
        # Validate response
        assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"
        assert data['status'] == 'success', f"Expected status 'success', got '{data['status']}'"
        assert 'stopped_count' in data, "Response missing 'stopped_count' field"
        
        # Verify that analyses were stopped
        assert data['stopped_count'] > 0, "Expected at least one analysis to be stopped"
        
        LOGGER.info("Stop-all successful, verified all analyses stopped")
    else:
        LOGGER.warning("Could not start any analyses, skipping stop-all test")
        pytest.skip("Could not start analyses to test stop-all functionality")

    LOGGER.info("Stop-all endpoint test passed!")
    LOGGER.info("<<<<<< Finished test_case test_stop_all_analyses_endpoint")


# TODO: Add here test for notify endpoint from     @blueprint.route('/notify', methods=['POST'])