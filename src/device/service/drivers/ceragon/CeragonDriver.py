# Copyright 2026 Ceragon Networks Ltd. & ETSI TeraFlowSDN Authors
#
# Licensed under the BSD 3-Clause License (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://opensource.org/licenses/BSD-3-Clause
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Ceragon Wireless Transport Southbound Driver for ETSI TeraFlowSDN
=================================================================
Manages Ceragon wireless radio links and transport equipment (MultiHaul TG,
EtherHaul, CeraOS) over RFC 8040 RESTCONF.

* Discovery reads the live datastore and reports Ethernet ports and radio
  sectors as TeraFlowSDN endpoints.
* SetConfig stages every rule of a request and commits them together on
  candidate-datastore devices; one failed rule discards the whole request.
* SubscribeState / GetState stream byte counters for Ethernet endpoints and
  link capacity (total and used, Gbps) for radio endpoints.
* GetConfig('/microwave-radio-link') returns an RFC 8561 view of the carriers.
"""
from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Any, Dict, Iterator, List, Optional, Tuple, Union

try:
    from common.method_wrappers.Decorator import MetricsPool, metered_subclass_method
except ModuleNotFoundError:
    class MetricsPool:  # type: ignore[no-redef]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

    def metered_subclass_method(_pool: Any) -> Any:  # type: ignore[no-redef]
        def _decorator(fn: Any) -> Any:
            return fn
        return _decorator

from device.service.driver_api._Driver import RESOURCE_ENDPOINTS, _Driver
from .client import CeragonRestClient
from .config import CeragonClientConfig
from .models import CeragonDeviceState
from .portfolio import ProductSpec
from .routing import apply_rule, delete_rule
from .Tools import (
    KPI_BYTES_RECEIVED, KPI_BYTES_TRANSMITTED, KPI_LINK_TOTAL_CAPACITY_GBPS, KPI_LINK_USED_CAPACITY_GBPS,
    MONITOR_KEY_RE, RESOURCE_RFC8561, compose_endpoints, compose_initial_config, compose_rfc8561_view,
    endpoint_counter, ethernet_ingress_octets, is_radio_endpoint, metric_to_kpi, sector_capacity_gbps,
)

LOGGER = logging.getLogger(__name__)

DRIVER_NAME = "ceragon"
METRICS_POOL = MetricsPool("Device", "Driver", labels={"driver": DRIVER_NAME})

SAMPLER_TICK_SECONDS = 0.5
MIN_SAMPLING_INTERVAL_SECONDS = 1.0


class CeragonDriver(_Driver):
    """ETSI TeraFlowSDN driver for Ceragon wireless transport devices."""

    def __init__(self, address: str, port: int, **settings) -> None:
        super().__init__(DRIVER_NAME, address, port, **settings)
        self.__lock = threading.RLock()          # one device transaction at a time
        self.__started = threading.Event()
        self.__terminate = threading.Event()

        self._client = CeragonRestClient(
            CeragonClientConfig.from_tfs_settings(self.address, self.port, self.settings)
        )
        self._state_cache: Optional[CeragonDeviceState] = None

        # Monitoring: resource_key -> (interval_s, expires_at or None)
        self.__subscriptions: Dict[str, Tuple[float, Optional[float]]] = {}
        self.__next_due: Dict[str, float] = {}
        self.__subscriptions_lock = threading.Lock()
        self.__samples: "queue.Queue[Tuple[float, str, Any]]" = queue.Queue()
        self.__sampler: Optional[threading.Thread] = None
        self.__last_ingress: Optional[Tuple[float, int]] = None

    # ── Lifecycle ───────────────────────────────────────────────────────────

    @metered_subclass_method(METRICS_POOL)
    def Connect(self) -> bool:
        """Probe the RESTCONF datastores and detect the device family."""
        with self.__lock:
            if self.__started.is_set():
                return True
            ok, msg = self._client.test_connection()
            if ok:
                self.__started.set()
                LOGGER.info("Ceragon device %s:%s connected: %s", self.address, self.port, msg)
                return True
            LOGGER.warning("Failed connecting to Ceragon device %s:%s: %s", self.address, self.port, msg)
            return False

    @metered_subclass_method(METRICS_POOL)
    def Disconnect(self) -> bool:
        """Stop the sampler and close the HTTP session."""
        self.__terminate.set()
        sampler = self.__sampler
        if sampler is not None and sampler.is_alive():
            sampler.join(timeout=5.0)
        with self.__lock:
            self._client._session.close()  # pylint: disable=protected-access
            self.__started.clear()
        LOGGER.info("Disconnected from Ceragon device %s:%s", self.address, self.port)
        return True

    # ── State helpers ──────────────────────────────────────────────────────

    def _refresh_state(self) -> CeragonDeviceState:
        with self.__lock:
            state = self._client.get_device_state()
            self._state_cache = state
            return state

    def _spec(self) -> Optional[ProductSpec]:
        if self._state_cache is None:
            try:
                self._refresh_state()
            except Exception as e:  # pylint: disable=broad-except
                LOGGER.debug("State prefetch failed, gating on the model hint only: %s", e)
        if self._state_cache is not None and self._state_cache.product_spec is not None:
            return self._state_cache.product_spec
        return self._client.hinted_spec

    # ── Discovery and reads ───────────────────────────────────────────────

    @metered_subclass_method(METRICS_POOL)
    def GetInitialConfig(self) -> List[Tuple[str, Any]]:
        """Device-level configuration: inventory, capabilities, sectors, RFC 8561 view."""
        state = self._refresh_state()
        return list(compose_initial_config(state))

    @metered_subclass_method(METRICS_POOL)
    def GetConfig(self, resource_keys: List[str] = []) -> List[Tuple[str, Union[Any, None, Exception]]]:  # pylint: disable=dangerous-default-value
        with self.__lock:
            try:
                state = self._refresh_state()
            except Exception as e:  # pylint: disable=broad-except
                LOGGER.exception("Unable to read Ceragon device state")
                return [(key, e) for key in (resource_keys or [RESOURCE_ENDPOINTS])]

            if not resource_keys:
                return list(compose_endpoints(state)) + list(compose_initial_config(state))

            device_rules = dict(compose_initial_config(state))
            results: List[Tuple[str, Union[Any, None, Exception]]] = []
            for key in resource_keys:
                try:
                    results.extend(self._read_resource(state, device_rules, key))
                except Exception as e:  # pylint: disable=broad-except
                    LOGGER.exception("Unable to read %s", key)
                    results.append((key, e))
            return results

    def _read_resource(
        self, state: CeragonDeviceState, device_rules: Dict[str, Any], key: str
    ) -> List[Tuple[str, Any]]:
        if key == RESOURCE_ENDPOINTS:
            return list(compose_endpoints(state))
        if key in device_rules:
            return [(key, device_rules[key])]
        if key == RESOURCE_RFC8561:
            return [(key, compose_rfc8561_view(state))]
        if key in ("/device/pm_telemetry", "/device/telemetry"):
            return [(key, self._client.fetch_pm_telemetry().to_dict())]
        if key == "/device/events":
            return [(key, {"events": self._client.fetch_events(limit=25)})]
        if key == "/device/yang_library":
            return [(key, self._client.get_yang_library())]
        if key.startswith("/yang/"):
            module = key.removeprefix("/yang/").strip("/")
            return [(key, {"module": module, "content": self._client.download_schema(module)})]
        if key.startswith("/restconf/"):
            ok, data = self._client.read_subtree(key.removeprefix("/restconf/").strip("/"))
            if not ok:
                return [(key, Exception(str(data)))]
            return [(key, data if isinstance(data, dict) else {"value": data})]
        return [(key, None)]

    # ── Configuration ─────────────────────────────────────────────────────

    def _run_batch(self, resources: List[Tuple[str, Any]], apply) -> List[Union[bool, Exception]]:
        """Stage every rule, then commit once (candidate datastores) or discard on any failure."""
        with self.__lock:
            outcomes: List[Tuple[bool, str, bool]] = []
            for key, value in resources:
                try:
                    outcomes.append(apply(key, value))
                except Exception as e:  # pylint: disable=broad-except
                    LOGGER.exception("Error staging %s", key)
                    outcomes.append((False, str(e), False))

            staged = any(changed for _, _, changed in outcomes)
            failed = any(not ok for ok, _, _ in outcomes)
            batch_error: Optional[str] = None
            if staged and self._client.device_flavor == "terragraph":
                if failed:
                    self._client.discard_candidate()
                    batch_error = "discarded: another rule in the same request failed"
                else:
                    ok, msg = self._client.commit_candidate()
                    if not ok:
                        self._client.discard_candidate()
                        batch_error = f"commit failed: {msg}"
            if staged and batch_error is None:
                self._state_cache = None  # re-read on next access

            results: List[Union[bool, Exception]] = []
            for (key, _), (ok, msg, changed) in zip(resources, outcomes):
                if not ok:
                    results.append(Exception(f"{key}: {msg}"))
                elif changed and batch_error is not None:
                    results.append(Exception(f"{key}: {batch_error}"))
                else:
                    results.append(True)
            return results

    @metered_subclass_method(METRICS_POOL)
    def SetConfig(self, resources: List[Tuple[str, Any]]) -> List[Union[bool, Exception]]:
        if len(resources) == 0:
            return []
        spec = self._spec()
        return self._run_batch(resources, lambda key, value: apply_rule(self._client, spec, key, value))

    @metered_subclass_method(METRICS_POOL)
    def DeleteConfig(self, resources: List[Tuple[str, Any]]) -> List[Union[bool, Exception]]:
        if len(resources) == 0:
            return []
        return self._run_batch(resources, lambda key, value: delete_rule(self._client, key, value))

    # ── Monitoring ────────────────────────────────────────────────────────

    @metered_subclass_method(METRICS_POOL)
    def SubscribeState(self, subscriptions: List[Tuple[str, float, float]]) -> List[Union[bool, Exception]]:
        results: List[Union[bool, Exception]] = []
        now = time.time()
        with self.__subscriptions_lock:
            for resource_key, duration, interval in subscriptions:
                m = MONITOR_KEY_RE.match(resource_key or "")
                if m is None or metric_to_kpi(m.group("metric")) is None:
                    results.append(Exception(f"Unsupported monitoring resource key: {resource_key}"))
                    continue
                interval = max(MIN_SAMPLING_INTERVAL_SECONDS, float(interval or 0) or 5.0)
                expires_at = now + float(duration) if duration and float(duration) > 0 else None
                self.__subscriptions[resource_key] = (interval, expires_at)
                self.__next_due[resource_key] = now
                results.append(True)
        if any(r is True for r in results):
            self._ensure_sampler()
        return results

    @metered_subclass_method(METRICS_POOL)
    def UnsubscribeState(self, subscriptions: List[Tuple[str, float, float]]) -> List[Union[bool, Exception]]:
        results: List[Union[bool, Exception]] = []
        with self.__subscriptions_lock:
            for resource_key, _, _ in subscriptions:
                removed = self.__subscriptions.pop(resource_key, None)
                self.__next_due.pop(resource_key, None)
                results.append(True if removed is not None else Exception(f"Not subscribed: {resource_key}"))
        return results

    def GetState(
        self, blocking=False, terminate: Optional[threading.Event] = None
    ) -> Iterator[Tuple[float, str, Any]]:
        while True:
            if self.__terminate.is_set():
                return
            if terminate is not None and terminate.is_set():
                return
            try:
                sample = self.__samples.get(block=blocking, timeout=0.1 if blocking else None)
            except queue.Empty:
                if blocking:
                    continue
                return
            yield sample

    def _ensure_sampler(self) -> None:
        if self.__sampler is not None and self.__sampler.is_alive():
            return
        self.__sampler = threading.Thread(target=self._sampler_loop, name=f"ceragon-sampler-{self.address}", daemon=True)
        self.__sampler.start()

    def _due_keys(self, now: float) -> List[str]:
        with self.__subscriptions_lock:
            for key, (_, expires_at) in list(self.__subscriptions.items()):
                if expires_at is not None and now >= expires_at:
                    self.__subscriptions.pop(key, None)
                    self.__next_due.pop(key, None)
            due = [k for k, t in self.__next_due.items() if now >= t]
            for key in due:
                self.__next_due[key] = now + self.__subscriptions[key][0]
            return due

    def _sampler_loop(self) -> None:
        while not self.__terminate.wait(SAMPLER_TICK_SECONDS):
            with self.__subscriptions_lock:
                if not self.__subscriptions:
                    continue
            due = self._due_keys(time.time())
            if not due:
                continue
            try:
                for sample in self.collect_samples(due):
                    self.__samples.put_nowait(sample)
            except Exception as e:  # pylint: disable=broad-except
                LOGGER.warning("Ceragon sampler: device poll failed: %s", e)

    def collect_samples(self, resource_keys: List[str]) -> List[Tuple[float, str, Any]]:
        """Poll the device once and compute a value for each monitoring resource key."""
        state = self._refresh_state()
        timestamp = time.time()
        used_gbps = self._used_capacity_gbps(state, timestamp)
        samples: List[Tuple[float, str, Any]] = []
        for key in resource_keys:
            m = MONITOR_KEY_RE.match(key)
            if m is None:
                continue
            endpoint, kpi = m.group("endpoint"), metric_to_kpi(m.group("metric"))
            value: Optional[float] = None
            if kpi in (KPI_BYTES_TRANSMITTED, KPI_BYTES_RECEIVED):
                value = endpoint_counter(state, endpoint, kpi)
            elif kpi == KPI_LINK_TOTAL_CAPACITY_GBPS and is_radio_endpoint(endpoint):
                value = sector_capacity_gbps(state, int(endpoint.rsplit("-", 1)[-1]))
            elif kpi == KPI_LINK_USED_CAPACITY_GBPS and is_radio_endpoint(endpoint):
                value = used_gbps
            if value is not None:
                samples.append((timestamp, key, value))
        return samples

    def _used_capacity_gbps(self, state: CeragonDeviceState, timestamp: float) -> Optional[float]:
        """
        Traffic offered to the radio, from Ethernet ingress counters between two polls.
        Reported per device until per-link byte counters are parsed.
        """
        octets = ethernet_ingress_octets(state)
        previous, self.__last_ingress = self.__last_ingress, (timestamp, octets)
        if previous is None:
            return None
        dt, delta = timestamp - previous[0], octets - previous[1]
        if dt <= 0 or delta < 0:  # clock step or counter wrap: skip this interval
            return None
        return round(delta * 8 / dt / 1e9, 6)
