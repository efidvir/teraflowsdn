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

import copy, grpc, json, logging, queue, threading
from typing import Any, Dict, List, Optional, Tuple, Union
from common.tools.grpc.Tools import grpc_message_to_json_string
from common.type_checkers.Checkers import chk_float, chk_length, chk_string, chk_type
from .gnmi.gnmi_pb2_grpc import gNMIStub
from .gnmi.gnmi_pb2 import Encoding, GetRequest, SetRequest, UpdateResult   # pylint: disable=no-name-in-module
from .handlers import ALL_RESOURCE_KEYS, compose, get_path, parse
from .handlers.Interface import EOS_TAGGED_L3_REPLACE_FIELD
from .handlers.YangHandler import YangHandler
from .tools.Capabilities import check_capabilities
from .tools.Channel import get_grpc_channel
from .tools.Path import path_from_string, path_to_string #, compose_path
from .tools.Subscriptions import Subscriptions
from .tools.Value import decode_value #, value_exists
from .MonitoringThread import MonitoringThread

INITIAL_TARGET_INFO_RESOURCE_KEY = '_info/gnmi/target'

DISCOVERY_PATH_SYSTEM_STATE = '/openconfig-system:system/state'
DISCOVERY_PATH_CHASSIS_STATE = '/openconfig-platform:components/component[name=Chassis]/state'


def _normalize_hint(value: Any) -> Optional[str]:
    if not isinstance(value, str): return None
    value = value.strip()
    if len(value) == 0: return None
    return value.lower()

def _extract_target_facts_from_system_state(system_state : Dict[str, Any]) -> Dict[str, str]:
    facts : Dict[str, str] = dict()
    hostname = system_state.get('openconfig-system:hostname')
    if isinstance(hostname, str) and len(hostname) > 0:
        facts['hostname'] = hostname

    software_version = system_state.get('openconfig-system:software-version')
    if isinstance(software_version, str) and len(software_version) > 0:
        facts['software_version'] = software_version

    return facts

def _extract_target_facts_from_chassis_state(chassis_state : Dict[str, Any]) -> Dict[str, str]:
    facts : Dict[str, str] = dict()

    vendor = chassis_state.get('openconfig-platform:mfg-name')
    if isinstance(vendor, str) and len(vendor) > 0:
        facts['vendor'] = vendor

    model = chassis_state.get('openconfig-platform:part-no')
    if isinstance(model, str) and len(model) > 0:
        facts['model'] = model

    description = chassis_state.get('openconfig-platform:description')
    if isinstance(description, str) and len(description) > 0:
        facts['description'] = description

    serial_no = chassis_state.get('openconfig-platform:serial-no')
    if isinstance(serial_no, str) and len(serial_no) > 0:
        facts['serial_no'] = serial_no

    return facts


def _is_arista_eos_target(settings: Dict[str, Any]) -> bool:
    hints = []
    target_facts = settings.get('_target_facts', {})
    if isinstance(target_facts, dict):
        for value in target_facts.values():
            normalized_value = _normalize_hint(value)
            if normalized_value is not None:
                hints.append(normalized_value)
    for key in ('vendor', 'platform', 'type', 'device_type', 'kind', 'model'):
        normalized_value = _normalize_hint(settings.get(key))
        if normalized_value is not None:
            hints.append(normalized_value)
    hint_blob = ' '.join(hints)
    return any(token in hint_blob for token in ('arista', 'ceos', 'eos'))


def _is_tagged_l3_access_subinterface(resource_key: str, resource_value: Dict[str, Any]) -> bool:
    if not resource_key.startswith('/interface['):
        return False
    if resource_value.get('vlan_id') is None:
        return False
    if resource_value.get('index') != 0:
        return False
    if resource_value.get('address_ip') is None or resource_value.get('address_prefix') is None:
        return False
    if resource_value.get('type') != 'l3ipvlan':
        return False
    return True


def _prepare_set_operation(
    settings: Dict[str, Any], resource_key: str, resource_value: Dict[str, Any]
) -> Tuple[str, Dict[str, Any]]:
    prepared_value = copy.deepcopy(resource_value)
    if _is_arista_eos_target(settings) and _is_tagged_l3_access_subinterface(resource_key, prepared_value):
        prepared_value[EOS_TAGGED_L3_REPLACE_FIELD] = True
        return 'replace', prepared_value
    return 'update', prepared_value

class GnmiSessionHandler:
    def __init__(self, address : str, port : int, settings : Dict, logger : logging.Logger) -> None:
        self._address   = address
        self._port      = port
        self._settings  = copy.deepcopy(settings)
        self._logger    = logger
        self._lock      = threading.Lock()
        self._connected = threading.Event()
        self._username  = settings.get('username')
        self._password  = settings.get('password')
        self._use_tls   = settings.get('use_tls', False)
        self._channel : Optional[grpc.Channel] = None
        self._stub : Optional[gNMIStub] = None
        self._monit_thread = None
        self._yang_handler = YangHandler()
        self._subscriptions = Subscriptions()
        self._in_subscriptions = queue.Queue()
        self._out_samples = queue.Queue()
        self._target_facts : Dict[str, Any] = dict()

    def __del__(self) -> None:
        self._logger.info('Destroying YangValidator...')
        if self._yang_handler is not None:
            self._logger.debug('yang_validator.data:')
            for path, dnode in self._yang_handler.get_data_paths().items():
                self._logger.debug('  {:s}: {:s}'.format(str(path), json.dumps(dnode.print_dict())))
            self._yang_handler.destroy()
        self._logger.info('DONE')

    @property
    def subscriptions(self): return self._subscriptions

    @property
    def in_subscriptions(self): return self._in_subscriptions

    @property
    def out_samples(self): return self._out_samples

    @property
    def target_facts(self): return copy.deepcopy(self._target_facts)

    def _merge_target_facts(self, target_facts : Optional[Dict[str, Any]]) -> None:
        if not isinstance(target_facts, dict): return
        for key, value in target_facts.items():
            if value is None: continue
            if isinstance(value, str) and len(value) == 0: continue
            self._target_facts[key] = value
        self._settings['_target_facts'] = copy.deepcopy(self._target_facts)

    def _get_discovery_value(self, str_path : str) -> Optional[Dict[str, Any]]:
        metadata = [('username', self._username), ('password', self._password)]

        get_request = GetRequest()
        get_request.type = GetRequest.DataType.STATE
        get_request.encoding = Encoding.JSON_IETF
        get_request.path.append(path_from_string(str_path))

        try:
            get_reply = self._stub.Get(get_request, metadata=metadata, timeout=30)
        except grpc.RpcError:
            self._logger.debug('Discovery probe failed for path=%s', str_path, exc_info=True)
            return None

        for notification in get_reply.notification:
            for update in notification.update:
                try:
                    value = decode_value(update.val)
                except Exception: # pylint: disable=broad-except
                    self._logger.debug('Discovery decode failed for path=%s', str_path, exc_info=True)
                    continue
                if isinstance(value, dict):
                    return value

        return None

    def _discover_target_facts(self, capability_info : Dict[str, Any]) -> None:
        self._merge_target_facts(capability_info.get('target_facts'))

        gnmi_version = capability_info.get('gnmi_version')
        if isinstance(gnmi_version, str) and len(gnmi_version) > 0:
            self._merge_target_facts({'gnmi_version': gnmi_version})

        system_state = self._get_discovery_value(DISCOVERY_PATH_SYSTEM_STATE)
        if isinstance(system_state, dict):
            self._merge_target_facts(_extract_target_facts_from_system_state(system_state))

        chassis_state = self._get_discovery_value(DISCOVERY_PATH_CHASSIS_STATE)
        if isinstance(chassis_state, dict):
            self._merge_target_facts(_extract_target_facts_from_chassis_state(chassis_state))

    def connect(self):
        with self._lock:
            self._channel = get_grpc_channel(self._address, self._port, self._use_tls, self._logger)
            self._stub = gNMIStub(self._channel)
            capability_info = check_capabilities(self._stub, self._username, self._password, timeout=120)
            self._discover_target_facts(capability_info)
            self._monit_thread = MonitoringThread(
                self._stub, self._logger, self._settings, self._in_subscriptions, self._out_samples)
            self._monit_thread.start()
            self._connected.set()

    def disconnect(self):
        if not self._connected.is_set(): return
        with self._lock:
            self._monit_thread.stop()
            self._monit_thread.join()
            self._channel.close()
            self._connected.clear()

    def get(self, resource_keys : List[str]) -> List[Tuple[str, Union[Any, None, Exception]]]:
        if len(resource_keys) == 0: resource_keys = ALL_RESOURCE_KEYS
        chk_type('resources', resource_keys, list)

        parsing_results = []

        get_request = GetRequest()
        get_request.type = GetRequest.DataType.ALL
        get_request.encoding = Encoding.JSON_IETF
        #get_request.use_models.add() # kept empty: return for all models supported
        for i,resource_key in enumerate(resource_keys):
            str_resource_name = 'resource_key[#{:d}]'.format(i)
            try:
                chk_string(str_resource_name, resource_key, allow_empty=False)
                self._logger.debug('[GnmiSessionHandler:get] resource_key = {:s}'.format(str(resource_key)))
                str_path = get_path(resource_key)
                self._logger.debug('[GnmiSessionHandler:get] str_path = {:s}'.format(str(str_path)))
                get_request.path.append(path_from_string(str_path))
            except Exception as e: # pylint: disable=broad-except
                MSG = 'Exception parsing {:s}: {:s}'
                self._logger.exception(MSG.format(str_resource_name, str(resource_key)))
                parsing_results.append((resource_key, e)) # if validation fails, store the exception

        self._logger.debug('parsing_results={:s}'.format(str(parsing_results)))

        if len(parsing_results) > 0:
            return parsing_results

        metadata = [('username', self._username), ('password', self._password)]
        timeout = None # GNMI_SUBSCRIPTION_TIMEOUT = int(sampling_duration)
        get_reply = self._stub.Get(get_request, metadata=metadata, timeout=timeout)
        self._logger.debug('get_reply={:s}'.format(grpc_message_to_json_string(get_reply)))

        results = []
        #results[str_filter] = [i, None, False]  # (index, value, processed?)

        for notification in get_reply.notification:
            #for delete_path in notification.delete:
            #    self._logger.info('delete_path={:s}'.format(grpc_message_to_json_string(delete_path)))
            #    str_path = path_to_string(delete_path)
            #    resource_key_tuple = results.get(str_path)
            #    if resource_key_tuple is None:
            #        # pylint: disable=broad-exception-raised
            #        MSG = 'Unexpected Delete Path({:s}); requested resource_keys({:s})'
            #        raise Exception(MSG.format(str(str_path), str(resource_keys)))
            #    resource_key_tuple[2] = True

            for update in notification.update:
                self._logger.debug('update={:s}'.format(grpc_message_to_json_string(update)))
                str_path = path_to_string(update.path)
                #resource_key_tuple = results.get(str_path)
                #if resource_key_tuple is None:
                #    # pylint: disable=broad-exception-raised
                #    MSG = 'Unexpected Update Path({:s}); requested resource_keys({:s})'
                #    raise Exception(MSG.format(str(str_path), str(resource_keys)))
                try:
                    value = decode_value(update.val)
                    #resource_key_tuple[1] = value
                    #resource_key_tuple[2] = True
                    results.extend(parse(str_path, value, self._yang_handler))
                except Exception as e: # pylint: disable=broad-except
                    MSG = 'Exception processing update {:s}'
                    self._logger.exception(MSG.format(grpc_message_to_json_string(update)))
                    results.append((str_path, e)) # if validation fails, store the exception

        #_results = sorted(results.items(), key=lambda x: x[1][0])
        #results = list()
        #for resource_key,resource_key_tuple in _results:
        #    _, value, processed = resource_key_tuple
        #    value = value if processed else Exception('Not Processed')
        #    results.append((resource_key, value))
        return results

    def set(self, resources : List[Tuple[str, Any]]) -> List[Union[bool, Exception]]:
        #resource_keys = [key for key,_ in resources]
        #current_values = self.get(resource_keys)

        #resource_tuples = {
        #    resource_key : [i, value, value_exists(value), None]
        #    for i,(resource_key,value) in enumerate(current_values)
        #}

        #self._logger.info('---0')
        #self._logger.info(str(resource_tuples))

        set_request = SetRequest()
        #for resource_key in resource_keys:
        resources_requested = list()
        for resource_key, resource_value in resources:
            #self._logger.info('---1')
            #self._logger.info(str(resource_key))
            #self._logger.info(str(resource_value))
            #resource_tuple = resource_tuples.get(resource_key)
            #if resource_tuple is None: continue
            #_, value, exists, operation_done = resource_tuple
            if isinstance(resource_value, str): resource_value = json.loads(resource_value)
            operation, prepared_value = _prepare_set_operation(self._settings, resource_key, resource_value)
            str_path, str_data = compose(resource_key, prepared_value, self._yang_handler, delete=False)
            if str_path is None: continue # nothing to set
            #self._logger.info('---3')
            #self._logger.info(str(str_path))
            #self._logger.info(str(str_data))
            set_request_list = set_request.replace if operation == 'replace' else set_request.update
            set_request_entry = set_request_list.add()
            set_request_entry.path.CopyFrom(path_from_string(str_path))
            set_request_entry.val.json_val = str_data.encode('UTF-8')
            resources_requested.append((len(resources_requested), resource_key, str_path, operation))

        self._logger.debug('set_request={:s}'.format(grpc_message_to_json_string(set_request)))
        metadata = [('username', self._username), ('password', self._password)]
        timeout = None # GNMI_SUBSCRIPTION_TIMEOUT = int(sampling_duration)
        set_reply = self._stub.Set(set_request, metadata=metadata, timeout=timeout)
        self._logger.debug('set_reply={:s}'.format(grpc_message_to_json_string(set_reply)))

        results = [
            (resource_key, Exception('Not Processed'))
            for _, resource_key, _, _ in resources_requested
        ]
        pending_requests = list(resources_requested)
        for update_result in set_reply.response:
            operation = update_result.op
            str_path = path_to_string(update_result.path)
            expected_operation = None
            if operation == UpdateResult.UPDATE:
                expected_operation = 'update'
            elif operation == UpdateResult.REPLACE:
                expected_operation = 'replace'

            matched = False
            if expected_operation is not None:
                for j, (resource_idx, resource_key, resource_path, requested_operation) in enumerate(pending_requests):
                    if resource_path == str_path and requested_operation == expected_operation:
                        results[resource_idx] = (resource_key, True)
                        pending_requests.pop(j)
                        matched = True
                        break

            if not matched:
                self._logger.warning(
                    'Unexpected Set reply operation=%s path=%s pending=%s',
                    str(operation), str(str_path), str(pending_requests)
                )

            #str_path = path_to_string(update_result.path)
            #resource_tuple = resource_tuples.get(str_path)
            #if resource_tuple is None: continue
            #resource_tuple[3] = operation

        #resource_tuples = sorted(resource_tuples.items(), key=lambda x: x[1][0])
        #results = list()
        #for resource_key,resource_tuple in resource_tuples:
        #    _, _, exists, operation_done = resource_tuple
        #    desired_operation = 'update' if exists else 'replace'
        #
        #    if operation_done == UpdateResult.INVALID:
        #        value = Exception('Invalid')
        #    elif operation_done == UpdateResult.DELETE:
        #        value = Exception('Unexpected Delete')
        #    elif operation_done == UpdateResult.REPLACE:
        #        value = True if desired_operation == 'replace' else Exception('Failed')
        #    elif operation_done == UpdateResult.UPDATE:
        #        value = True if desired_operation == 'update' else Exception('Failed')
        #    else:
        #        value = Exception('Unexpected')
        #    results.append((resource_key, value))
        return results

    def delete(self, resources : List[Tuple[str, Any]]) -> List[Union[bool, Exception]]:
        #resource_keys = [key for key,_ in resources]
        #current_values = self.get(resource_keys)

        #resource_tuples = {
        #    resource_key : [i, value, value_exists(value), None]
        #    for i,(resource_key,value) in enumerate(current_values)
        #}

        #self._logger.info('---0')
        #self._logger.info(str(resource_tuples))

        set_request = SetRequest()
        #for resource_key in resource_keys:
        resources_requested = list()
        for resource_key, resource_value in resources:
            #self._logger.info('---1')
            #self._logger.info(str(resource_key))
            #self._logger.info(str(resource_value))
            #resource_tuple = resource_tuples.get(resource_key)
            #if resource_tuple is None: continue
            #_, value, exists, operation_done = resource_tuple
            #if not exists: continue
            if isinstance(resource_value, str): resource_value = json.loads(resource_value)
            # pylint: disable=unused-variable
            str_path, str_data = compose(resource_key, resource_value, self._yang_handler, delete=True)
            if str_path is None: continue # nothing to do with this resource_key
            #self._logger.info('---3')
            #self._logger.info(str(str_path))
            #self._logger.info(str(str_data))
            set_request_entry = set_request.delete.add()
            set_request_entry.CopyFrom(path_from_string(str_path))
            resources_requested.append((resource_key, resource_value))

        self._logger.debug('set_request={:s}'.format(grpc_message_to_json_string(set_request)))
        metadata = [('username', self._username), ('password', self._password)]
        timeout = None # GNMI_SUBSCRIPTION_TIMEOUT = int(sampling_duration)
        set_reply = self._stub.Set(set_request, metadata=metadata, timeout=timeout)
        self._logger.debug('set_reply={:s}'.format(grpc_message_to_json_string(set_reply)))

        results = []
        for (resource_key, resource_value), update_result in zip(resources_requested, set_reply.response):
            operation = update_result.op
            if operation == UpdateResult.DELETE:
                results.append((resource_key, True))
            else:
                results.append((resource_key, Exception('Unexpected')))

            #str_path = path_to_string(update_result.path)
            #resource_tuple = resource_tuples.get(str_path)
            #if resource_tuple is None: continue
            #resource_tuple[3] = operation

        #resource_tuples = sorted(resource_tuples.items(), key=lambda x: x[1][0])
        #results = list()
        #for resource_key,resource_tuple in resource_tuples:
        #    _, _, exists, operation_done = resource_tuple
        #    if operation_done == UpdateResult.INVALID:
        #        value = Exception('Invalid')
        #    elif operation_done == UpdateResult.DELETE:
        #        value = True
        #    elif operation_done == UpdateResult.REPLACE:
        #        value = Exception('Unexpected Replace')
        #    elif operation_done == UpdateResult.UPDATE:
        #        value = Exception('Unexpected Update')
        #    else:
        #        value = Exception('Unexpected')
        #    results.append((resource_key, value))
        return results

    def subscribe(self, subscriptions : List[Tuple[str, float, float]]) -> List[Union[bool, Exception]]:
        results = []
        for i,subscription in enumerate(subscriptions):
            str_subscription_name = 'subscriptions[#{:d}]'.format(i)
            try:
                chk_type(str_subscription_name, subscription, (list, tuple))
                chk_length(str_subscription_name, subscription, min_length=3, max_length=3)
                resource_key, sampling_duration, sampling_interval = subscription
                chk_string(str_subscription_name + '.resource_key', resource_key, allow_empty=False)
                chk_float(str_subscription_name + '.sampling_duration', sampling_duration, min_value=0)
                chk_float(str_subscription_name + '.sampling_interval', sampling_interval, min_value=0)
            except Exception as e: # pylint: disable=broad-except
                MSG = 'Exception validating {:s}: {:s}'
                self._logger.exception(MSG.format(str_subscription_name, str(resource_key)))
                results.append(e) # if validation fails, store the exception
                continue

            #resource_path = resource_key.split('/')
            #self._subscriptions.add(resource_path, sampling_duration, sampling_interval, reference)
            subscription = 'subscribe', resource_key, sampling_duration, sampling_interval
            self._in_subscriptions.put_nowait(subscription)
            results.append(True)
        return results

    def unsubscribe(self, subscriptions : List[Tuple[str, float, float]]) -> List[Union[bool, Exception]]:
        results = []
        for i,subscription in enumerate(subscriptions):
            str_subscription_name = 'subscriptions[#{:d}]'.format(i)
            try:
                chk_type(str_subscription_name, subscription, (list, tuple))
                chk_length(str_subscription_name, subscription, min_length=3, max_length=3)
                resource_key, sampling_duration, sampling_interval = subscription
                chk_string(str_subscription_name + '.resource_key', resource_key, allow_empty=False)
                chk_float(str_subscription_name + '.sampling_duration', sampling_duration, min_value=0)
                chk_float(str_subscription_name + '.sampling_interval', sampling_interval, min_value=0)
            except Exception as e: # pylint: disable=broad-except
                MSG = 'Exception validating {:s}: {:s}'
                self._logger.exception(MSG.format(str_subscription_name, str(resource_key)))
                results.append(e) # if validation fails, store the exception
                continue

            #resource_path = resource_key.split('/')
            #reference = self._subscriptions.get(resource_path, sampling_duration, sampling_interval)
            #if reference is None:
            #    results.append(False)
            #    continue
            #self._subscriptions.delete(reference)
            subscription = 'unsubscribe', resource_key, sampling_duration, sampling_interval
            self._in_subscriptions.put_nowait(subscription)
            results.append(True)
        return results
