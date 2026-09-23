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

from enum import Enum
from typing import Any, Dict, Optional
from common.proto.context_pb2 import Device, DeviceDriverEnum, Service, ServiceTypeEnum

class FilterFieldEnum(Enum):
    SERVICE_TYPE  = 'service_type'
    DEVICE_DRIVER = 'device_driver'

SERVICE_TYPE_VALUES = {
    ServiceTypeEnum.SERVICETYPE_UNKNOWN,
    ServiceTypeEnum.SERVICETYPE_L3NM,
    ServiceTypeEnum.SERVICETYPE_L2NM,
    ServiceTypeEnum.SERVICETYPE_L1NM,
    ServiceTypeEnum.SERVICETYPE_TAPI_CONNECTIVITY_SERVICE,
    ServiceTypeEnum.SERVICETYPE_TE,
    ServiceTypeEnum.SERVICETYPE_E2E,
    ServiceTypeEnum.SERVICETYPE_OPTICAL_CONNECTIVITY,
    ServiceTypeEnum.SERVICETYPE_QKD,
    ServiceTypeEnum.SERVICETYPE_INT,
    ServiceTypeEnum.SERVICETYPE_ACL,
    ServiceTypeEnum.SERVICETYPE_IP_LINK,
    ServiceTypeEnum.SERVICETYPE_IPOWDM,
    ServiceTypeEnum.SERVICETYPE_TAPI_LSP,
    ServiceTypeEnum.SERVICETYPE_UPF,
}

DEVICE_DRIVER_VALUES = {
    DeviceDriverEnum.DEVICEDRIVER_UNDEFINED,
    DeviceDriverEnum.DEVICEDRIVER_OPENCONFIG,
    DeviceDriverEnum.DEVICEDRIVER_TRANSPORT_API,
    DeviceDriverEnum.DEVICEDRIVER_P4,
    DeviceDriverEnum.DEVICEDRIVER_IETF_NETWORK_TOPOLOGY,
    DeviceDriverEnum.DEVICEDRIVER_ONF_TR_532,
    DeviceDriverEnum.DEVICEDRIVER_XR,
    DeviceDriverEnum.DEVICEDRIVER_IETF_L2VPN,
    DeviceDriverEnum.DEVICEDRIVER_GNMI_OPENCONFIG,
    DeviceDriverEnum.DEVICEDRIVER_OPTICAL_TFS,
    DeviceDriverEnum.DEVICEDRIVER_IETF_ACTN,
    DeviceDriverEnum.DEVICEDRIVER_OC,
    DeviceDriverEnum.DEVICEDRIVER_QKD,
    DeviceDriverEnum.DEVICEDRIVER_IETF_L3VPN,
    DeviceDriverEnum.DEVICEDRIVER_IETF_SLICE,
    DeviceDriverEnum.DEVICEDRIVER_NCE,
    DeviceDriverEnum.DEVICEDRIVER_SMARTNIC,
    DeviceDriverEnum.DEVICEDRIVER_MORPHEUS,
    DeviceDriverEnum.DEVICEDRIVER_RYU,
    DeviceDriverEnum.DEVICEDRIVER_GNMI_NOKIA_SRLINUX,
    DeviceDriverEnum.DEVICEDRIVER_OPENROADM,
    DeviceDriverEnum.DEVICEDRIVER_RESTCONF_OPENCONFIG,
}

# Map allowed filter fields to allowed values per Filter field. If no restriction (free text) None is specified
FILTER_FIELD_ALLOWED_VALUES = {
    FilterFieldEnum.SERVICE_TYPE.value  : set(ServiceTypeEnum.values()),
    FilterFieldEnum.DEVICE_DRIVER.value : set(DeviceDriverEnum.values()),
}

def get_service_handler_filter_fields(
    service : Optional[Service], device : Optional[Device]
) -> Dict[FilterFieldEnum, Any]:
    if service is None: return {}
    if device is None: return {}
    return {
        FilterFieldEnum.SERVICE_TYPE  : service.service_type,
        FilterFieldEnum.DEVICE_DRIVER : [driver for driver in device.device_drivers],
    }
