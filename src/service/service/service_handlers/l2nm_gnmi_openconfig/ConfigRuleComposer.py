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

import json, logging
from typing import Dict, List, Optional, Set, Tuple
from common.DeviceTypes import DeviceTypeEnum
from common.proto.context_pb2 import Device, EndPoint, Service
from common.tools.grpc.Tools import grpc_message_to_json_string
from common.tools.object_factory.ConfigRule import json_config_rule_delete, json_config_rule_set
from service.service.service_handler_api.AnyTreeTools import TreeNode

LOGGER = logging.getLogger(__name__)

#NETWORK_INSTANCE = 'teraflowsdn' # TODO: investigate; sometimes it does not create/delete static rules properly
NETWORK_INSTANCE = 'default'
DEFAULT_NETWORK_INSTANCE = 'default'

def _safe_int(value: Optional[object]) -> Optional[int]:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None

def _safe_bool(value: Optional[object]) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {'true', '1', 'yes', 'y', 'on', 'tagged'}:
            return True
        if lowered in {'false', '0', 'no', 'n', 'off', 'untagged'}:
            return False
    return None

def _interface_switched_vlan(
    interface : str, interface_mode : str, access_vlan_id : Optional[int] = None,
    trunk_vlan_id : Optional[int] = None, native_vlan : int = 1
) -> Tuple[str, Dict]:
    path = '/interface[{:s}]/ethernet/switched-vlan'.format(interface)
    config : Dict[str, object] = {'interface-mode': interface_mode}
    if interface_mode == 'ACCESS':
        if access_vlan_id is not None:
            config['access-vlan'] = access_vlan_id
    elif interface_mode == 'TRUNK':
        config['native-vlan'] = native_vlan
        if trunk_vlan_id is not None:
            config['trunk-vlans'] = [trunk_vlan_id]
    return path, {'config': config}

def _network_instance(ni_name : str, ni_type : str) -> Tuple[str, Dict]:
    path = '/network_instance[{:s}]'.format(ni_name)
    data = {'name': ni_name, 'type': ni_type}
    return path, data

def _network_instance_vlan(ni_name : str, vlan_id : int, vlan_name : str = None) -> Tuple[str, Dict]:
    path = '/network_instance[{:s}]/vlan[{:s}]'.format(ni_name, str(vlan_id))
    data = {'name': ni_name, 'vlan_id': vlan_id, 'vlan_name': vlan_name}
    return path, data


class EndpointComposer:
    def __init__(self, endpoint_uuid : str) -> None:
        self.uuid = endpoint_uuid
        self.objekt : Optional[EndPoint] = None
        self.explicit_vlan_ids : Set[int] = set()
        self.force_trunk = False

    def _add_vlan_id(self, vlan_id : Optional[int]) -> None:
        if vlan_id is not None:
            self.explicit_vlan_ids.add(vlan_id)

    def _configure_from_settings(self, json_settings : Dict) -> None:
        if not isinstance(json_settings, dict):
            return
        vlan_id = _safe_int(json_settings.get('vlan_id', json_settings.get('vlan-id')))
        self._add_vlan_id(vlan_id)

    def configure(self, endpoint_obj : Optional[EndPoint], settings : Optional[TreeNode]) -> None:
        if endpoint_obj is not None:
            self.objekt = endpoint_obj
        if settings is None: return

        json_settings : Dict = settings.value or dict()
        self._configure_from_settings(json_settings)
        for child in settings.children:
            if isinstance(child.value, dict):
                self._configure_from_settings(child.value)

    def set_force_trunk(self, enable : bool = True) -> None:
        self.force_trunk = enable

    def _select_trunk_vlan_id(self, service_vlan_id : int) -> int:
        if service_vlan_id in self.explicit_vlan_ids:
            return service_vlan_id
        if len(self.explicit_vlan_ids) > 0:
            return sorted(self.explicit_vlan_ids)[0]
        return service_vlan_id

    def get_vlan_ids(self) -> Set[int]:
        return set(self.explicit_vlan_ids)

    def has_vlan(self, vlan_id : int) -> bool:
        return vlan_id in self.get_vlan_ids()

    def get_config_rules(
        self, service_vlan_id : int, access_vlan_tagged : bool = False, delete : bool = False
    ) -> List[Dict]:
        if self.objekt is None:
            MSG = 'Endpoint object not defined for uuid={:s}'
            LOGGER.warning(MSG.format(self.uuid))
            return []
        config_rules : List[Dict] = list()
        json_config_rule = json_config_rule_delete if delete else json_config_rule_set
        if self.force_trunk or access_vlan_tagged or len(self.explicit_vlan_ids) > 0:
            trunk_vlan_id = self._select_trunk_vlan_id(service_vlan_id)
            config_rules.append(json_config_rule(*_interface_switched_vlan(
                self.objekt.name, 'TRUNK', trunk_vlan_id=trunk_vlan_id
            )))
        else:
            config_rules.append(json_config_rule(*_interface_switched_vlan(
                self.objekt.name, 'ACCESS', access_vlan_id=service_vlan_id
            )))
        return config_rules

    def dump(self) -> Dict:
        return {
            'explicit_vlan_ids' : list(self.explicit_vlan_ids),
            'force_trunk' : self.force_trunk,
        }

    def __str__(self):
        data = {'uuid': self.uuid}
        if self.objekt is not None: data['name'] = self.objekt.name
        data.update(self.dump())
        return json.dumps(data)

class DeviceComposer:
    def __init__(self, device_uuid : str) -> None:
        self.uuid = device_uuid
        self.objekt : Optional[Device] = None
        self.aliases : Dict[str, str] = dict() # endpoint_name => endpoint_uuid
        self.endpoints : Dict[str, EndpointComposer] = dict() # endpoint_uuid => EndpointComposer
        self.vlan_ids : Set[int] = set()

    def set_endpoint_alias(self, endpoint_name : str, endpoint_uuid : str) -> None:
        self.aliases[endpoint_name] = endpoint_uuid

    def get_endpoint(self, endpoint_uuid : str) -> EndpointComposer:
        endpoint_uuid = self.aliases.get(endpoint_uuid, endpoint_uuid)
        if endpoint_uuid not in self.endpoints:
            self.endpoints[endpoint_uuid] = EndpointComposer(endpoint_uuid)
        return self.endpoints[endpoint_uuid]

    def _refresh_vlan_ids(self, service_vlan_id : int) -> None:
        # Only keep the service VLAN; others are ignored for composition
        self.vlan_ids = {service_vlan_id}

    def configure(self, device_obj : Device, settings : Optional[TreeNode]) -> None:
        self.objekt = device_obj
        for endpoint_obj in device_obj.device_endpoints:
            endpoint_uuid = endpoint_obj.endpoint_id.endpoint_uuid.uuid
            self.set_endpoint_alias(endpoint_obj.name, endpoint_uuid)
            self.get_endpoint(endpoint_obj.name).configure(endpoint_obj, None)

    def get_config_rules(
        self, network_instance_name : str, service_vlan_id : int,
        access_vlan_tagged : bool = False, delete : bool = False
    ) -> List[Dict]:
        SELECTED_DEVICES = {
            DeviceTypeEnum.PACKET_POP.value,
            DeviceTypeEnum.PACKET_ROUTER.value,
            DeviceTypeEnum.EMULATED_PACKET_ROUTER.value
        }
        if self.objekt.device_type not in SELECTED_DEVICES: return []

        json_config_rule = json_config_rule_delete if delete else json_config_rule_set
        config_rules : List[Dict] = list()
        self._refresh_vlan_ids(service_vlan_id)
        if network_instance_name != DEFAULT_NETWORK_INSTANCE:
            json_config_rule(*_network_instance(network_instance_name, 'L3VRF'))
        for endpoint in self.endpoints.values():
            config_rules.extend(endpoint.get_config_rules(
                service_vlan_id, access_vlan_tagged=access_vlan_tagged, delete=delete
            ))
        for vlan_id in sorted(self.vlan_ids):
            vlan_name = 'tfs-vlan-{:s}'.format(str(vlan_id))
            config_rules.append(json_config_rule(*_network_instance_vlan(
                network_instance_name, vlan_id, vlan_name=vlan_name
            )))
        if delete: config_rules = list(reversed(config_rules))
        return config_rules

    def dump(self) -> Dict:
        return {
            'endpoints' : {
                endpoint_uuid : endpoint.dump()
                for endpoint_uuid, endpoint in self.endpoints.items()
            },
            'vlan_ids' : list(self.vlan_ids)
        }

    def __str__(self):
        data = {'uuid': self.uuid}
        if self.objekt is not None: data['name'] = self.objekt.name
        data.update(self.dump())
        return json.dumps(data)

class ConfigRuleComposer:
    def __init__(self) -> None:
        self.objekt : Optional[Service] = None
        self.aliases : Dict[str, str] = dict() # device_name => device_uuid
        self.devices : Dict[str, DeviceComposer] = dict() # device_uuid => DeviceComposer
        self.vlan_id = None
        self.access_vlan_tagged = False

    def set_device_alias(self, device_name : str, device_uuid : str) -> None:
        self.aliases[device_name] = device_uuid

    def get_device(self, device_uuid : str) -> DeviceComposer:
        device_uuid = self.aliases.get(device_uuid, device_uuid)
        if device_uuid not in self.devices:
            self.devices[device_uuid] = DeviceComposer(device_uuid)
        return self.devices[device_uuid]

    def configure(self, service_obj : Service, settings : Optional[TreeNode]) -> None:
        self.objekt = service_obj
        if settings is None:
            raise Exception('Service settings are required to extract vlan_id')
        json_settings : Dict = settings.value or dict()

        if 'vlan_id' in json_settings:
            self.vlan_id = _safe_int(json_settings['vlan_id'])
        elif 'vlan-id' in json_settings:
            self.vlan_id = _safe_int(json_settings['vlan-id'])
        else:
            MSG = 'VLAN ID not found. Tried: vlan_id and vlan-id. service_obj={:s} settings={:s}'
            raise Exception(MSG.format(grpc_message_to_json_string(service_obj), str(settings)))

        if self.vlan_id is None:
            MSG = 'Invalid VLAN ID value in service settings: {:s}'
            raise Exception(MSG.format(str(json_settings)))

        access_vlan_tagged = json_settings.get('access_vlan_tagged', json_settings.get('access-vlan-tagged'))
        if access_vlan_tagged is None:
            self.access_vlan_tagged = False
        else:
            parsed = _safe_bool(access_vlan_tagged)
            if parsed is None:
                MSG = 'Invalid access_vlan_tagged value in service settings: {:s}'
                LOGGER.warning(MSG.format(str(access_vlan_tagged)))
                self.access_vlan_tagged = False
            else:
                self.access_vlan_tagged = parsed

    def get_config_rules(
        self, network_instance_name : str = NETWORK_INSTANCE, delete : bool = False
    ) -> Dict[str, List[Dict]]:
        if self.vlan_id is None:
            raise Exception('VLAN ID must be configured at service level before composing rules')

        return {
            device_uuid : device.get_config_rules(
                network_instance_name, self.vlan_id,
                access_vlan_tagged=self.access_vlan_tagged, delete=delete
            )
            for device_uuid, device in self.devices.items()
        }

    def dump(self) -> Dict:
        return {
            'devices' : {
                device_uuid : device.dump()
                for device_uuid, device in self.devices.items()
            },
            'vlan_id': self.vlan_id,
            'access_vlan_tagged': self.access_vlan_tagged,
        }
