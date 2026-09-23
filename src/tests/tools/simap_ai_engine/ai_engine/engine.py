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
AI Engine orchestrator.

Main class that initializes and coordinates all AI Engine components.
"""

import logging

from flask import Flask

from .config import Config
from .api.api_blueprint import create_ai_engine_blueprint
from .clients.decision_client import DecisionEngineClient
from .clients.influxdb_fetcher import InfluxDBFetcher
from .clients.simap_fetcher import SimapDataFetcher
from .ai_model.ai_processor import AIModelProcessor

LOGGER = logging.getLogger(__name__)


class AIEngineAPI:
    """
    Main orchestrator for the AI Engine REST API.

    This class initializes all components and manages the Flask application
    lifecycle.
    """

    def __init__(self) -> None:
        """
        Initialize the AI Engine API.

        Creates instances of all required components (fetchers, processor,
        client) and configures the Flask application with the API blueprint.
        """
        LOGGER.info("Initializing AI Engine API")

        # Initialize components
        self.simap_fetcher = SimapDataFetcher(
            simap_scheme   = Config.SIMAP_DATASTORE_SCHEME,
            simap_address  = Config.SIMAP_DATASTORE_ADDRESS,
            simap_port     = Config.SIMAP_DATASTORE_PORT,
            simap_username = Config.SIMAP_DATASTORE_USERNAME,
            simap_password = Config.SIMAP_DATASTORE_PASSWORD
        )

        self.influxdb_fetcher = InfluxDBFetcher(
            influxdb_host     = Config.INFLUXDB_HOST,
            influxdb_port     = Config.INFLUXDB_PORT,
            influxdb_token    = Config.INFLUXDB_TOKEN,
            influxdb_database = Config.INFLUXDB_DATABASE
        )

        # Pass InfluxDB fetcher to AI processor for writing predicted telemetry
        self.ai_processor = AIModelProcessor(
            influx_fetcher=self.influxdb_fetcher
        )
        self.decision_client = DecisionEngineClient()

        # Create Flask application
        self.app = self.create_app()

    def create_app(self) -> Flask:
        """
        Create and configure the Flask application.

        Returns:
            Configured Flask application instance.
        """
        app = Flask(__name__)

        # Register the AI Engine blueprint
        blueprint = create_ai_engine_blueprint(
            simap_fetcher    = self.simap_fetcher,
            influxdb_fetcher = self.influxdb_fetcher,
            ai_processor     = self.ai_processor,
            decision_client  = self.decision_client
        )
        app.register_blueprint(blueprint)

        LOGGER.info("Flask application created and blueprint registered")
        return app

    def run(self) -> None:
        """
        Run the Flask application.

        Starts the Flask development server with the configured host and port.
        """
        LOGGER.info(
            f"Starting AI Engine API on "
            f"{Config.AI_ENGINE_REST_HOST}:{Config.AI_ENGINE_REST_PORT}"
        )
        self.app.run(
            host=Config.AI_ENGINE_REST_HOST,
            port=Config.AI_ENGINE_REST_PORT,
            debug=False
        )
