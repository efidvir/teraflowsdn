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
Flask Blueprint for AI Engine REST API.

Defines the REST API endpoints for the AI Engine.
"""

import logging
import threading
import time
from datetime import datetime, timezone


from flask import Blueprint, jsonify, request
import requests

from ..config import Config
from ..ai_model.ai_processor import AIModelProcessor
from ..clients.decision_client import DecisionEngineClient
from ..clients.influxdb_fetcher import InfluxDBFetcher
from ..clients.simap_fetcher import SimapDataFetcher
from ..ai_model.sla_policy import SLAPolicyConfig

LOGGER = logging.getLogger(__name__)

# Background analysis state - track multiple analyses by simap_id
_analysis_threads = {}  # {simap_id: {'thread': Thread, 'stop_event': Event}}
_threads_lock = threading.Lock()

# OSM endpoint configuration
END_HOST = '10.0.58.25'
END_PORT = 8084
BASE_URL = f'http://{END_HOST}:{END_PORT}/osm/aiAnalyticsEvent/v1'


def create_ai_engine_blueprint(
    simap_fetcher: SimapDataFetcher,
    influxdb_fetcher: InfluxDBFetcher,
    ai_processor:     AIModelProcessor,
    decision_client:  DecisionEngineClient
) -> Blueprint:

    blueprint = Blueprint('ai_analytics', __name__, url_prefix='/api/v1')

    def _background_analysis_task(sla_policy: SLAPolicyConfig, duration_minutes: int, stop_event: threading.Event):
        """
        Background task that periodically analyzes data and posts results.
        Args:
            sla_policy: SLA policy configuration for analysis.
            duration_minutes: How long to run the analysis (in minutes).
            stop_event: Threading event to signal task termination.
        """
        simap_id = sla_policy.simap_id
        _response = {}
        
        try:
            LOGGER.info(f"[{simap_id}] Starting background analysis for {duration_minutes} minutes")
            start_time = time.time()
            end_time   = start_time + (duration_minutes * 60)
            iteration  = 0
            
            while time.time() < end_time and not stop_event.is_set():
                iteration += 1
                iteration_start = time.time()
                
                try:
                    LOGGER.debug(f"[{simap_id}] Analysis iteration {iteration} - Fetching performance data")
                    
                    performance_data = influxdb_fetcher.fetch_performance_data(sla_policy)
                    
                    LOGGER.debug(f"[{simap_id}] Analysis iteration {iteration} - Processing with AI models")
                    results = ai_processor.process_data(performance_data)
                    
                    results['simap_id']  = simap_id
                    # results['iteration'] = iteration

                    _response['data'] = results
                    _response['status'] = 'success'
                    _response['message'] = f'Analysis completed successfully'

                    
                    LOGGER.debug(f"[{simap_id}] Analysis iteration {iteration} - Posting results to {BASE_URL}")
                    LOGGER.debug(f"[{simap_id}] Results payload: {_response}")
                    response = requests.post(
                        BASE_URL,
                        json    = _response,
                        timeout = 10,
                        headers = {'Content-Type': 'application/json'}
                    )
                    
                    if response.status_code in (200, 201, 202):
                        LOGGER.info(f"[{simap_id}] Iteration {iteration}: Results posted successfully (status {response.status_code})")
                    else:
                        LOGGER.warning(f"[{simap_id}] Iteration {iteration}: POST returned status {response.status_code}: {response.text}")
                    
                except Exception as e:
                    LOGGER.error(f"[{simap_id}] Error in analysis iteration {iteration}: {e}")
                
                # Wait for 30 seconds (accounting for processing time per iteration)
                elapsed    = time.time() - iteration_start
                sleep_time = max(0, 30   - elapsed)
                
                if sleep_time > 0 and time.time() + sleep_time < end_time and not stop_event.is_set():
                    LOGGER.debug(f"[{simap_id}] Sleeping for {sleep_time:.1f} seconds until next iteration")
                    stop_event.wait(timeout=sleep_time)  # Use wait instead of sleep for immediate response
                elif time.time() < end_time:
                    # Not enough time for another full iteration cycle, exit gracefully
                    LOGGER.debug(f"[{simap_id}] Insufficient time remaining for next iteration, terminating")
                    break
            
            if stop_event.is_set():
                LOGGER.info(f"[{simap_id}] Background analysis stopped after {iteration} iterations")
            else:
                LOGGER.info(f"[{simap_id}] Background analysis completed after {iteration} iterations. Time limit reached.")
            
        except Exception as e:
            LOGGER.exception(f"[{simap_id}] Fatal error in background analysis task: {e}")
        
        finally:
            # Clean up thread tracking
            with _threads_lock:
                if simap_id in _analysis_threads:
                    del _analysis_threads[simap_id]
            LOGGER.info(f"[{simap_id}] Background analysis task terminated")

    @blueprint.route('/analyze', methods=['POST'])
    def analyze():
        """
        Start SLA policy analysis in background.

        Expects JSON payload with SLA policy configuration including duration_minutes.
        Validates input and immediately returns 202 Accepted.
        Analysis runs in background, posting results every 30 seconds for the specified duration.

        Returns:
            JSON response with acceptance confirmation or error message.
        """
        LOGGER.info("Received analysis request")

        # Parse and validate request JSON
        try:
            data = request.get_json()
            if data is None:
                LOGGER.error("Request body is empty or not valid JSON")
                return jsonify({
                    'status': 'error',
                    'message': 'Request body must be valid JSON'
                }), 400
        except Exception as e:
            LOGGER.error(f"Failed to parse request JSON: {e}")
            return jsonify({
                'status': 'error',
                'message': f'Invalid JSON: {str(e)}'
            }), 400

        # Validate and create SLAPolicyConfig
        try:
            sla_policy = SLAPolicyConfig.from_dict(data)
            LOGGER.info(f"Processing SLA policy for SIMAP ID: {sla_policy.simap_id}")
        except KeyError as e:
            LOGGER.error(f"Missing required field in request: {e}")
            return jsonify({
                'status': 'error',
                'message': f'Missing required field: {str(e)}'
            }), 400
        except (TypeError, ValueError) as e:
            LOGGER.error(f"Invalid field value in request: {e}")
            return jsonify({
                'status': 'error',
                'message': f'Invalid field value: {str(e)}'
            }), 400
        
        # Extract duration from request
        try:
            duration_minutes = int(data.get('duration_minutes', 0))
            if duration_minutes <= 0:
                raise ValueError("duration_minutes must be positive")
        except (TypeError, ValueError) as e:
            LOGGER.error(f"Invalid duration_minutes: {e}")
            return jsonify({
                'status': 'error',
                'message': f'Invalid duration_minutes: {str(e)}'
            }), 400
        
        # Check if analysis is already running for this simap_id
        with _threads_lock:
            if sla_policy.simap_id in _analysis_threads:
                thread_info = _analysis_threads[sla_policy.simap_id]
                if thread_info['thread'].is_alive():
                    LOGGER.warning(f"Analysis request rejected: analysis for SIMAP ID {sla_policy.simap_id} is already running")
                    return jsonify({
                        'status': 'error',
                        'message': f'Analysis for SIMAP ID {sla_policy.simap_id} is already running. Stop it first.'
                    }), 409  # Conflict
        
        # Start background analysis task
        try:
            stop_event = threading.Event()
            analysis_thread = threading.Thread(
                target=_background_analysis_task,
                args=(sla_policy, duration_minutes, stop_event),
                daemon=True,
                name=f"AI-Analysis-Thread-{sla_policy.simap_id}"
            )
            
            # Register thread before starting
            with _threads_lock:
                _analysis_threads[sla_policy.simap_id] = {
                    'thread':           analysis_thread,
                    'stop_event':       stop_event,
                    'start_time':       datetime.now(timezone.utc).isoformat(),
                    'duration_minutes': duration_minutes
                }
            
            analysis_thread.start()
            
            LOGGER.info(f"Background analysis started for SIMAP ID {sla_policy.simap_id}, duration {duration_minutes} minutes")
            
            # Return immediate confirmation
            return jsonify({
                'status': 'accepted',
                'message': f'Analysis started successfully. Results will be posted every 30 seconds for {duration_minutes} minutes.',
                'simap_id': sla_policy.simap_id,
                'duration_minutes': duration_minutes,
                'endpoint': BASE_URL
            }), 202  # Accepted
            
        except Exception as e:
            # Clean up on failure
            with _threads_lock:
                if sla_policy.simap_id in _analysis_threads:
                    del _analysis_threads[sla_policy.simap_id]
            LOGGER.exception(f"Failed to start background analysis: {e}")
            return jsonify({
                'status': 'error',
                'message': f'Failed to start analysis: {str(e)}'
            }), 500

    @blueprint.route('/analyze/stop', methods=['POST'])
    def stop_analyze():
        """
        Stop running analysis for a specific SIMAP ID.

        Expects JSON payload with simap_id.
        Signals the background thread to stop gracefully.

        Returns:
            JSON response with stop confirmation or error message.
        """
        LOGGER.info("Received stop analysis request")

        # Parse and validate request JSON
        try:
            data = request.get_json()
            if data is None:
                LOGGER.error("Request body is empty or not valid JSON")
                return jsonify({
                    'status': 'error',
                    'message': 'Request body must be valid JSON'
                }), 400
        except Exception as e:
            LOGGER.error(f"Failed to parse request JSON: {e}")
            return jsonify({
                'status': 'error',
                'message': f'Invalid JSON: {str(e)}'
            }), 400

        # Extract simap_id
        simap_id = data.get('simap_id')
        if not simap_id:
            LOGGER.error("Missing simap_id in request")
            return jsonify({
                'status': 'error',
                'message': 'Missing required field: simap_id'
            }), 400

        # Find and stop the thread
        with _threads_lock:
            if simap_id not in _analysis_threads:
                LOGGER.warning(f"No running analysis found for SIMAP ID {simap_id}")
                return jsonify({
                    'status': 'error',
                    'message': f'No running analysis found for SIMAP ID {simap_id}'
                }), 404
            
            thread_info = _analysis_threads[simap_id]
            if not thread_info['thread'].is_alive():
                # Clean up dead thread
                del _analysis_threads[simap_id]
                LOGGER.warning(f"Analysis thread for SIMAP ID {simap_id} is not alive")
                return jsonify({
                    'status': 'error',
                    'message': f'Analysis for SIMAP ID {simap_id} is not running'
                }), 404
            
            # Signal thread to stop
            thread_info['stop_event'].set()
            LOGGER.info(f"Stop signal sent to analysis thread for SIMAP ID {simap_id}")
        
        return jsonify({
            'status': 'success',
            'message': f'Stop signal sent to analysis for SIMAP ID {simap_id}',
            'simap_id': simap_id
        }), 200

    @blueprint.route('/analyze/stop-all', methods=['POST'])
    def stop_all_analyses():
        """
        Stop all running analyses.

        Signals all background threads to stop gracefully.

        Returns:
            JSON response with summary of stopped analyses.
        """
        LOGGER.info("Received stop all analyses request")

        stopped_ids = []
        skipped_ids = []
        
        with _threads_lock:
            if not _analysis_threads:
                LOGGER.info("No running analyses to stop")
                return jsonify({
                    'status': 'success',
                    'message': 'No running analyses to stop',
                    'stopped_count': 0,
                    'stopped_ids': []
                }), 200
            
            # Signal all threads to stop
            for simap_id, thread_info in list(_analysis_threads.items()):
                if thread_info['thread'].is_alive():
                    thread_info['stop_event'].set()
                    stopped_ids.append(simap_id)
                    LOGGER.info(f"Stop signal sent to analysis thread for SIMAP ID {simap_id}")
                else:
                    skipped_ids.append(simap_id)
                    LOGGER.warning(f"Analysis thread for SIMAP ID {simap_id} is not alive, skipping")
        
        return jsonify({
            'status': 'success',
            'message': f'Stop signal sent to {len(stopped_ids)} running analyses',
            'stopped_count': len(stopped_ids),
        }), 200

    @blueprint.route('/status', methods=['GET'])
    def status():
        """
        Get status of all running analyses.

        Returns:
            JSON response with list of running analyses.
        """
        LOGGER.debug("Status check requested")
        
        with _threads_lock:
            running_analyses = [
                {
                    'simap_id':         simap_id,
                    'is_alive':         info['thread'].is_alive(),
                    'start_time':       info['start_time'],
                    'duration_minutes': info['duration_minutes']
                }
                for simap_id, info in _analysis_threads.items()
            ]
        
        return jsonify({
            'running_count': len(running_analyses),
            'analyses': running_analyses,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }), 200



    @blueprint.route('/health', methods=['GET'])
    def health():
        """
        Health check endpoint.

        Returns:
            JSON response with service health status.
        """
        LOGGER.debug("Health check requested")
        return jsonify({
            'status': 'healthy',
            'service': 'AI Engine',
            'timestamp': datetime.now(timezone.utc).isoformat()
        }), 200

    @blueprint.route('/config', methods=['GET'])
    def config():
        """
        Get current configuration.

        Returns:
            JSON response with SIMAP and InfluxDB connection details.
            Sensitive values (passwords, tokens) are masked.
        """
        LOGGER.debug("Configuration requested")
        
        def mask_secret(value: str) -> str:
            """Mask sensitive values for display."""
            if not value:
                return '(not set)'
            return f"{value[:2]}{'*' * (len(value) - 2)}" if len(value) > 2 else '***'
        
        return jsonify({
            'simap': {
                'scheme': Config.SIMAP_DATASTORE_SCHEME,
                'address': Config.SIMAP_DATASTORE_ADDRESS,
                'port': Config.SIMAP_DATASTORE_PORT,
                'username': Config.SIMAP_DATASTORE_USERNAME,
                'password': mask_secret(Config.SIMAP_DATASTORE_PASSWORD)
            },
            'influxdb': {
                'host': Config.INFLUXDB_HOST,
                'port': Config.INFLUXDB_PORT,
                'token': mask_secret(Config.INFLUXDB_TOKEN),
                'database': Config.INFLUXDB_DATABASE
            },
            'api': {
                'host': Config.AI_ENGINE_REST_HOST,
                'port': Config.AI_ENGINE_REST_PORT
            }
        }), 200

    @blueprint.route('/notify', methods=['POST'])
    def notify():
        """
        Handle telemetry update notifications.

        Accepts status notifications (UPGRADE or DOWNGRADE) with optional
        timestamp, validates the payload structure, and forwards to
        InfluxDBFetcher for storage.

        Expected JSON payload:
            {
                "status": "UPGRADE" | "DOWNGRADE",  # Required, uppercase only
                "timestamp": "<any string>"          # Optional
            }

        Returns:
            JSON response with success/error status.
        """
        LOGGER.info("Received telemetry notification request")

        # Parse and validate request JSON
        try:
            data = request.get_json()
            if data is None:
                LOGGER.error("Request body is empty or not valid JSON")
                return jsonify({
                    'status': 'error',
                    'message': 'Request body must be valid JSON'
                }), 400
        except Exception as e:
            LOGGER.error(f"Failed to parse request JSON: {e}")
            return jsonify({
                'status': 'error',
                'message': f'Invalid JSON: {str(e)}'
            }), 400

        # Validate payload structure
        try:
            # Check for unexpected keys
            allowed_keys = {'status', 'timestamp'}
            received_keys = set(data.keys())
            unexpected_keys = received_keys - allowed_keys
            if unexpected_keys:
                LOGGER.error(f"Unexpected keys in payload: {unexpected_keys}")
                return jsonify({
                    'status': 'error',
                    'message': f'Unexpected keys: {", ".join(unexpected_keys)}'
                }), 400

            # Check for required 'status' key
            if 'status' not in data:
                LOGGER.error("Missing required field: status")
                return jsonify({
                    'status': 'error',
                    'message': 'Missing required field: status'
                }), 400

            # Validate status value
            status_value = data['status']
            if status_value not in {'UPGRADE', 'DOWNGRADE'}:
                LOGGER.error(f"Invalid status value: {status_value}")
                return jsonify({
                    'status': 'error',
                    'message': 'Invalid status value: must be UPGRADE or DOWNGRADE'
                }), 400

            # Validate timestamp if present (accept any string)
            if 'timestamp' in data and not isinstance(data['timestamp'], str):
                LOGGER.error(f"Invalid timestamp type: {type(data['timestamp'])}")
                return jsonify({
                    'status': 'error',
                    'message': 'Timestamp must be a string'
                }), 400

            LOGGER.debug(f"Payload validation passed for status: {status_value}")

        except Exception as e:
            LOGGER.error(f"Payload validation error: {e}")
            return jsonify({
                'status': 'error',
                'message': f'Validation error: {str(e)}'
            }), 400

        # Forward to InfluxDBFetcher
        try:
            result = influxdb_fetcher.notify_telemetry_update(data)
            if result:
                LOGGER.info("Telemetry notification processed successfully")
                return jsonify({
                    'status': 'success',
                    'message': 'Notification processed successfully'
                }), 200
            else:
                LOGGER.error("InfluxDBFetcher returned False")
                return jsonify({
                    'status': 'error',
                    'message': 'Failed to process notification'
                }), 500

        except ValueError as e:
            # Validation errors from InfluxDBFetcher
            LOGGER.error(f"Validation error from InfluxDBFetcher: {e}")
            return jsonify({
                'status': 'error',
                'message': str(e)
            }), 400

        except Exception as e:
            # Check if this is a retry failure (service unavailable)
            error_msg = str(e)
            if 'Giving up' in error_msg or 'unavailable' in error_msg.lower():
                LOGGER.error(f"InfluxDB unavailable: {e}")
                return jsonify({
                    'status': 'error',
                    'message': f'InfluxDB service unavailable: {error_msg}'
                }), 503
            else:
                LOGGER.exception(f"Unexpected error processing notification: {e}")
                return jsonify({
                    'status': 'error',
                    'message': f'Internal server error: {error_msg}'
                }), 500

    return blueprint
