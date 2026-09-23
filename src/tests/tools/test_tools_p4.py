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

from common.Constants import DEFAULT_CONTEXT_NAME
from common.proto.context_pb2 import ContextId, DeviceOperationalStatusEnum,\
    DeviceDriverEnum, ServiceTypeEnum, ServiceStatusEnum
from common.tools.object_factory.Context import json_context_id

# Context info
CONTEXT_NAME_P4 = DEFAULT_CONTEXT_NAME
ADMIN_CONTEXT_ID = ContextId(**json_context_id(CONTEXT_NAME_P4))

# Device and rule cardinality variables
DEV_NB = 4
P4_DEV_NB = 1

# Service-related variables
SVC_NB = 1
NO_SERVICES = 0
NO_SLICES = 0

def identify_number_of_p4_devices(devices) -> int:
    p4_dev_no = 0

    # Iterate all devices
    for device in devices:
        # Skip non-P4 devices
        if not DeviceDriverEnum.DEVICEDRIVER_P4 in device.device_drivers: continue

        p4_dev_no += 1
    
    return p4_dev_no

def get_number_of_rules(devices) -> int:
    total_rules_no = 0

    # Iterate all devices
    for device in devices:
        # Skip non-P4 devices
        if not DeviceDriverEnum.DEVICEDRIVER_P4 in device.device_drivers: continue

        # We want the device to be active
        assert device.device_operational_status == \
            DeviceOperationalStatusEnum.DEVICEOPERATIONALSTATUS_ENABLED

        # Get the configuration rules of this device
        config_rules = device.device_config.config_rules

        # Expected rule cardinality
        total_rules_no += len(config_rules)
    
    return total_rules_no

def verify_number_of_rules(devices, desired_rules_nb : int) -> None:
    # Iterate all devices
    for device in devices:
        # Skip non-P4 devices
        if not DeviceDriverEnum.DEVICEDRIVER_P4 in device.device_drivers: continue

        # We want the device to be active
        assert device.device_operational_status == \
            DeviceOperationalStatusEnum.DEVICEOPERATIONALSTATUS_ENABLED

        # Get the configuration rules of this device
        config_rules = device.device_config.config_rules

        # Expected rule cardinality
        assert len(config_rules) == desired_rules_nb

def verify_active_service_type(services, target_service_type : ServiceTypeEnum) -> bool: # type: ignore
    # Iterate all services
    for service in services:
        # Ignore services of other types
        if service.service_type != target_service_type:
            continue

        service_id = service.service_id
        assert service_id
        assert service.service_status.service_status == ServiceStatusEnum.SERVICESTATUS_ACTIVE
        assert service.service_config
        return True
    
    return False
