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

import grpc
import common.tools.grpc.BaseEventCollector as base_event_collector_module
import context.client.EventsCollector as context_events_module
from common.proto.context_pb2 import DeviceEvent, EventTypeEnum


class _FakeRpcError(grpc.RpcError):
    def __init__(self, status_code):
        self._status_code = status_code

    def code(self):
        return self._status_code


class _FakeStream:
    def __init__(self, events=None):
        self._events = iter(events or [])

    def __iter__(self):
        return self

    def __next__(self):
        return next(self._events)

    def cancel(self):
        pass


class _FakeContextClient:
    def __init__(self):
        self.calls = 0

    def GetDeviceEvents(self, _request):
        self.calls += 1
        if self.calls == 1:
            raise _FakeRpcError(grpc.StatusCode.UNAVAILABLE)
        if self.calls == 2:
            return _FakeStream(events=[_create_device_event()])
        raise _FakeRpcError(grpc.StatusCode.CANCELLED)


def _create_device_event():
    event = DeviceEvent()
    event.event.event_type = EventTypeEnum.EVENTTYPE_CREATE
    event.event.timestamp.timestamp = 1.0
    event.device_id.device_uuid.uuid = 'dev1'
    return event


def test_events_collector_retries_if_subscription_creation_fails(monkeypatch):
    monkeypatch.setattr(base_event_collector_module.time, 'sleep', lambda _seconds: None)

    collector = context_events_module.EventsCollector(
        _FakeContextClient(),
        activate_context_collector=False,
        activate_topology_collector=False,
        activate_device_collector=True,
        activate_link_collector=False,
        activate_service_collector=False,
        activate_slice_collector=False,
        activate_connection_collector=False,
    )

    collector.start()
    try:
        event = collector.get_event(block=True, timeout=1.0)
    finally:
        collector.stop()

    assert event.device_id.device_uuid.uuid == 'dev1'
