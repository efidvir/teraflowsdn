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

import logging
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional, Set, Tuple, Type
from common.proto.context_pb2 import Device, DeviceDriverEnum, Service
from common.tools.grpc.Tools import grpc_message_to_json_string
from .Exceptions import (
    AmbiguousFilterException, EmptyFilterFieldException,
    UnsatisfiedFilterException, UnsupportedServiceHandlerClassException,
    UnsupportedFilterFieldException, UnsupportedFilterFieldValueException
)
from .FilterFields import FILTER_FIELD_ALLOWED_VALUES, FilterFieldEnum

if TYPE_CHECKING:
    from ._ServiceHandler import _ServiceHandler


LOGGER = logging.getLogger(__name__)

SUPPORTED_FILTER_FIELDS = set(FILTER_FIELD_ALLOWED_VALUES.keys())


def check_is_class_valid(service_handler_class : Type['_ServiceHandler']) -> None:
    from ._ServiceHandler import _ServiceHandler
    if not issubclass(service_handler_class, _ServiceHandler):
        raise UnsupportedServiceHandlerClassException(str(service_handler_class))

def sanitize_filter_fields(
    filter_fields : Dict[FilterFieldEnum, Any], service_handler_name : Optional[str] = None
) -> Dict[FilterFieldEnum, Any]:
    if len(filter_fields) == 0:
        raise EmptyFilterFieldException(
            filter_fields, service_handler_class_name=service_handler_name
        )

    unsupported_filter_fields = set(filter_fields.keys()).difference(SUPPORTED_FILTER_FIELDS)
    if len(unsupported_filter_fields) > 0:
        raise UnsupportedFilterFieldException(
            unsupported_filter_fields, service_handler_class_name=service_handler_name
        )

    sanitized_filter_fields : Dict[FilterFieldEnum, Set[Any]] = dict()
    for field_name, field_values in filter_fields.items():
        field_enum_values = FILTER_FIELD_ALLOWED_VALUES.get(field_name)
        if not isinstance(field_values, Iterable) or isinstance(field_values, str):
            field_values = [field_values]
        
        sanitized_field_values : Set[Any] = set()
        for field_value in field_values:
            if isinstance(field_value, Enum): field_value = field_value.value
            if field_enum_values is not None and field_value not in field_enum_values:
                raise UnsupportedFilterFieldValueException(
                    field_name, field_value, field_enum_values,
                    service_handler_class_name=service_handler_name
                )
            sanitized_field_values.add(field_value)
        
        if len(sanitized_field_values) == 0: continue # do not add empty filters
        sanitized_filter_fields[field_name] = sanitized_field_values
    
    return sanitized_filter_fields


class ServiceHandlerFactory:
    def __init__(
        self, service_handlers : List[Tuple[Type['_ServiceHandler'], List[Dict[FilterFieldEnum, Any]]]]
    ) -> None:
        self.__service_handlers : List[Tuple[Type['_ServiceHandler'], Dict[FilterFieldEnum, Any]]] = list()

        for service_handler_class,filter_field_sets in service_handlers:
            check_is_class_valid(service_handler_class)
            service_handler_name = service_handler_class.__name__

            for filter_fields in filter_field_sets:
                filter_fields = {k.value:v for k,v in filter_fields.items()}
                filter_fields = sanitize_filter_fields(
                    filter_fields, service_handler_name=service_handler_name
                )
                self.__service_handlers.append((service_handler_class, filter_fields))


    def is_service_handler_compatible(
        self, service_handler_filter_fields : Dict[FilterFieldEnum, Any],
        selection_filter_fields : Dict[FilterFieldEnum, Any]
    ) -> bool:
        # by construction empty service_handler_filter_fields are not allowed
        # by construction empty selection_filter_fields are not allowed
        for filter_field in SUPPORTED_FILTER_FIELDS:
            service_handler_values = set(service_handler_filter_fields.get(filter_field, set()))
            if service_handler_values is None  : continue # means service_handler does not restrict
            if len(service_handler_values) == 0: continue # means service_handler does not restrict

            selection_values = set(selection_filter_fields.get(filter_field, set()))
            is_field_compatible = selection_values.issubset(service_handler_values)
            if not is_field_compatible: return False

        return True


    def get_service_handler_class(self, **selection_filter_fields) -> '_ServiceHandler':
        sanitized_filter_fields = sanitize_filter_fields(selection_filter_fields)

        compatible_service_handlers : List[Tuple[Type[_ServiceHandler], Dict[FilterFieldEnum, Any]]] = [
            service_handler_class
            for service_handler_class,service_handler_filter_fields in self.__service_handlers
            if self.is_service_handler_compatible(service_handler_filter_fields, sanitized_filter_fields)
        ]

        MSG = '[get_service_handler_class] compatible_service_handlers={:s}'
        LOGGER.debug(MSG.format(str(compatible_service_handlers)))

        num_compatible = len(compatible_service_handlers)
        if num_compatible == 0: 
            raise UnsatisfiedFilterException(selection_filter_fields)
        if num_compatible > 1:
            raise AmbiguousFilterException(selection_filter_fields, compatible_service_handlers)
        return compatible_service_handlers[0]

def get_common_device_drivers(drivers_per_device : List[Set[int]]) -> Set[int]:
    common_device_drivers = None
    for device_drivers in drivers_per_device:
        if common_device_drivers is None:
            common_device_drivers = set(device_drivers)
        else:
            common_device_drivers.intersection_update(device_drivers)
    if common_device_drivers is None: common_device_drivers = set()
    return common_device_drivers

def get_service_handler_class(
    service_handler_factory : ServiceHandlerFactory, service : Service,
    device_and_drivers: Dict[str, Tuple[Device, Set[int]]]
) -> Optional['_ServiceHandler']:
    str_service_key = grpc_message_to_json_string(service.service_id)
    # Checks if the service is of type ipowdm
    if 'ipowdm' in str(service.service_config.config_rules):
        common_device_drivers = [DeviceDriverEnum.DEVICEDRIVER_IETF_L3VPN]
    # Checks if the service is of type tapi_lsp
    elif 'tapi_lsp' in str(service.service_config.config_rules):
        common_device_drivers = [DeviceDriverEnum.DEVICEDRIVER_TRANSPORT_API]
    else:
        common_device_drivers = get_common_device_drivers([
            device_drivers
            for _,device_drivers in device_and_drivers.values()
        ])
    LOGGER.debug('common_device_drivers={:s}'.format(str(common_device_drivers)))

    filter_fields = {
        FilterFieldEnum.SERVICE_TYPE.value  : service.service_type,     # must be supported
        FilterFieldEnum.DEVICE_DRIVER.value : common_device_drivers,    # at least one must be supported
    }

    MSG = 'Selecting service handler for service({:s}) with filter_fields({:s})...'
    LOGGER.info(MSG.format(str(str_service_key), str(filter_fields)))
    service_handler_class = service_handler_factory.get_service_handler_class(**filter_fields)
    MSG = 'ServiceHandler({:s}) selected for service({:s}) with filter_fields({:s})...'
    LOGGER.info(MSG.format(str(service_handler_class.__name__), str(str_service_key), str(filter_fields)))
    return service_handler_class
