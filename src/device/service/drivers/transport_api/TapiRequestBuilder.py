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

import json
import logging
import os
import requests

LOGGER = logging.getLogger(__name__)

def create_tapi_request(resource_value):
    """Create TAPI connectivity service request from resource value.

    Args:
        resource_value: Tuple of (resource_key, resource_data_dict)

    Returns:
        dict: TAPI connectivity service request payload
    """
    LOGGER.info("Creating TAPI request for resource_value: %s", resource_value)
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(base_dir, 'templates', 'lsp.json')
        with open(json_path, 'r', encoding='utf-8') as f:
            template = json.load(f)

        resource_key = resource_value[0]
        resource_data = json.loads(resource_value[1]) if isinstance(resource_value[1], str) else resource_value[1]

        LOGGER.info("Processing resource_key: %s", resource_key)
        LOGGER.info("Resource data: %s", resource_data)

        svc = template["tapi-connectivity:connectivity-service"][0]
        svc["connectivity-direction"] = resource_data["direction"]
        svc["layer-protocol-name"] = resource_data["layer_protocol_name"]
        svc["layer-protocol-qualifier"] = resource_data["layer_protocol_qualifier"]
        svc["requested-capacity"]["total-size"]["unit"] = "GHz"
        svc["requested-capacity"]["total-size"]["value"] = resource_data["bw"]
        svc["include-link"] = resource_data.get("link_uuid_path", [])
        svc["uuid"] = resource_data["uuid"]

        ep0 = svc["end-point"][0]
        ep0["service-interface-point"]["service-interface-point-uuid"] = resource_data["input_sip"]
        ep0["direction"] = resource_data["direction"]
        ep0["layer-protocol-name"] = resource_data["layer_protocol_name"]
        ep0["layer-protocol-qualifier"] = resource_data["layer_protocol_qualifier"]
        ep0["local-id"] = resource_data["input_sip"]

        media_spec = ep0["tapi-photonic-media:media-channel-connectivity-service-end-point-spec"]
        mc_config = media_spec["mc-config"]
        spectrum = mc_config["spectrum"]
        spectrum["lower-frequency"] = resource_data["lower_frequency_mhz"]
        spectrum["upper-frequency"] = resource_data["upper_frequency_mhz"]
        spectrum["frequency-constraint"]["adjustment-granularity"] = resource_data["granularity"]
        spectrum["frequency-constraint"]["grid-type"] = resource_data["grid_type"]

        ep1 = svc["end-point"][1]
        ep1["service-interface-point"]["service-interface-point-uuid"] = resource_data["output_sip"]
        ep1["direction"] = resource_data["direction"]
        ep1["layer-protocol-name"] = resource_data["layer_protocol_name"]
        ep1["layer-protocol-qualifier"] = resource_data["layer_protocol_qualifier"]
        ep1["local-id"] = resource_data["output_sip"]

        url = resource_data.get("url", "")

        LOGGER.info("URL: %s", url)
        LOGGER.info("Template: %s", json.dumps(template, indent = 2))
        headers = {
            "Content-Type": "application/yang-data+json",
            "Accept": "application/yang-data+json",
            "Expect": ""
        }
        result = requests.post(url, headers=headers, data=json.dumps(template), timeout=10)
        return result

    except (OSError, json.JSONDecodeError, KeyError) as e:
        LOGGER.error("Error creating TAPI request: %s", str(e), exc_info=True)
        raise
