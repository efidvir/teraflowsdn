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
SIMAP Data Fetcher module.

Provides functionality to fetch device and topology data from the SIMAP server.
"""

import logging
from typing import Any, Dict

from common.tools.client.RetryDecorator import delay_exponential, retry

from ..ai_model.sla_policy import SLAPolicyConfig

LOGGER = logging.getLogger(__name__)

# Retry decorator for external service calls
RETRY_DECORATOR = retry(
    max_retries=5,
    delay_function=delay_exponential(initial=0.01, increment=2.0, maximum=5.0)
)


class SimapDataFetcher:
    """
    Fetches device and topology data from the SIMAP server.

    This class handles communication with the SIMAP server to retrieve
    device configurations and network topology information needed for
    SLA policy analysis.
    """

    def __init__(
        self,
        simap_scheme: str,
        simap_address: str,
        simap_port: int,
        simap_username: str,
        simap_password: str
    ) -> None:
        """
        Initialize the SimapDataFetcher.

        Args:
            simap_scheme: URL scheme for SIMAP server (http/https).
            simap_address: SIMAP server hostname or IP address.
            simap_port: SIMAP server port number.
            simap_username: Username for SIMAP authentication.
            simap_password: Password for SIMAP authentication.
        """
        self.simap_scheme   = simap_scheme
        self.simap_address  = simap_address
        self.simap_port     = simap_port
        self.simap_username = simap_username
        self.simap_password = simap_password
        self.base_url       = f"{simap_scheme}://{simap_address}:{simap_port}"
        LOGGER.info(f"SimapDataFetcher initialized with base URL: {self.base_url}")

    @RETRY_DECORATOR
    def fetch_device_data(self, sla_policy: SLAPolicyConfig) -> Dict[str, Any]:
        """
        Fetch device and topology data from the SIMAP server.

        Communicates with the SIMAP server to retrieve device configurations
        and network topology information relevant to the given SLA policy.
        The retry decorator ensures resilience against transient failures.

        Args:
            sla_policy: The SLA policy configuration containing the SIMAP ID
                and parameters for data retrieval.

        Returns:
            Dictionary containing:
                - 'devices': List of device configurations.
                - 'topology': Network topology information.

        Raises:
            Exception: If the SIMAP server is unavailable after all retries,
                or if the response is invalid.
        """
        LOGGER.debug(f"Fetching device data for SIMAP ID: {sla_policy.simap_id}")
        # TODO: Implement actual SIMAP server communication
        # Example implementation:
        # url = f"{self.base_url}/api/devices/{sla_policy.simap_id}"
        # response = requests.get(url, auth=(self.simap_username, self.simap_password))
        # response.raise_for_status()
        # return response.json()
        return {
            'devices': [],
            'topology': {},
            'simap_id': sla_policy.simap_id
        }
