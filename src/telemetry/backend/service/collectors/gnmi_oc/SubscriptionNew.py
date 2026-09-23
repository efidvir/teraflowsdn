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


import time
from pygnmi.client import gNMIclient  # type: ignore
from queue import Queue
from typing import Callable, Tuple, Optional, List, Any
import grpc
import json
import logging
import threading

LOGGER = logging.getLogger(__name__)
# LOGGER.setLevel(logging.INFO)


class Subscription:
    """
    Handles a gNMI *Subscribe* session.
    It receives a **list of candidate paths**; if the target rejects one
    (INVALID_ARGUMENT / unknown path), the thread automatically tries the
    next path until it works or the list is exhausted.
    """

    def __init__(
        self,
        sub_id:                str,
        gnmi_client:           gNMIclient,
        path_list:             List[str],
        metric_queue:          Queue,
        mode:                  str             = "stream",
        sample_interval_ns:    int             = 10_000_000_000,
        heartbeat_interval_ns: Optional[int]   = None,
        total_duration:        Optional[float] = None,                  # in seconds
        encoding:              str             = "json_ietf",
        on_update:             Optional[Callable[[dict], None]] = None,
    ) -> None:

        self.sub_id        = sub_id
        self.gnmi_client   = gnmi_client
        self._queue: Queue = metric_queue
        self._stop_event   = threading.Event()

        self._thread       = threading.Thread(
            target = self._run,
            args   = (
                path_list, mode, sample_interval_ns, 
                heartbeat_interval_ns, encoding, on_update,
            ),
            name=f"gnmi-sub-{sub_id[:8]}",
            daemon=True,
        )
        # Start the subscription thread
        self._thread.start()
        
        # Stop the subscription after the given duration
        if total_duration and total_duration > 0:
            def stop_after_duration():
                time.sleep(total_duration)
                LOGGER.warning(f"Execution duration ({total_duration}s) completed for Subscription: {sub_id}")
                self.stop()

            duration_thread = threading.Thread(
                target=stop_after_duration, daemon=True, name=f"stop_after_duration_{sub_id[:8]}"
            )
            duration_thread.start()
        else:
            LOGGER.debug("Subscription %s has no total duration limit", sub_id)

        LOGGER.info("Started subscription %s",sub_id)
    # --------------------------------------------------------------#
    #  Public helpers                                               #
    # --------------------------------------------------------------#
    def get(self, timeout: Optional[float] = None) -> dict:
        return self._queue.get(timeout=timeout)

    def stop(self) -> None:
        """Gracefully stop the subscription thread."""
        if not self._thread.is_alive():
            LOGGER.debug("Subscription %s thread already stopped", self.sub_id)
            return
        
        LOGGER.debug("Stopping subscription %s...", self.sub_id)
        self._stop_event.set()
        self._thread.join(timeout=3)
        
        if self._thread.is_alive():
            LOGGER.warning("Subscription %s thread did not stop within timeout", self.sub_id)
        else:
            LOGGER.info("Stopped subscription %s", self.sub_id)

    # --------------------------------------------------------------#
    #  Internal loop                                                #
    # --------------------------------------------------------------#
    def _parse_subscribe_response(self, stream_msg) -> dict:
        """
        Parse gNMI SubscribeResponse protobuf message.
        Mimics pygnmi's telemetryParser but simplified for our needs.
        Properly decodes json_ietf_val by directly accessing protobuf bytes.
        """
        response = {}
        
        if stream_msg.HasField("update"):
            response["update"] = {
                "timestamp": stream_msg.update.timestamp if stream_msg.update.timestamp else 0,
                "update": []
            }
            
            # Process updates
            for update_msg in stream_msg.update.update:
                update_container = {
                    "path": self._gnmi_path_to_string(update_msg.path) if update_msg.path else None
                }
                
                # Decode the value - THIS IS THE KEY PART
                if update_msg.HasField("val"):
                    if update_msg.val.HasField("json_ietf_val"):
                        # Access raw bytes and decode directly (like pygnmi does)
                        decoded_val = json.loads(update_msg.val.json_ietf_val)
                        # Try to convert numeric strings to float for proper formatting
                        if isinstance(decoded_val, str):
                            try:
                                decoded_val = float(decoded_val)
                            except (ValueError, TypeError):
                                pass  # Keep as string if not numeric
                        update_container["val"] = decoded_val
                    elif update_msg.val.HasField("json_val"):
                        decoded_val = json.loads(update_msg.val.json_val)
                        # Try to convert numeric strings to float
                        if isinstance(decoded_val, str):
                            try:
                                decoded_val = float(decoded_val)
                            except (ValueError, TypeError):
                                pass
                        update_container["val"] = decoded_val
                    elif update_msg.val.HasField("string_val"):
                        update_container["val"] = update_msg.val.string_val
                    elif update_msg.val.HasField("int_val"):
                        update_container["val"] = update_msg.val.int_val
                    elif update_msg.val.HasField("uint_val"):
                        update_container["val"] = update_msg.val.uint_val
                    elif update_msg.val.HasField("bool_val"):
                        update_container["val"] = update_msg.val.bool_val
                    elif update_msg.val.HasField("float_val"):
                        update_container["val"] = update_msg.val.float_val
                    else:
                        update_container["val"] = None
                
                response["update"]["update"].append(update_container)
        
        elif stream_msg.HasField("sync_response"):
            response["sync_response"] = stream_msg.sync_response
        
        return response
    
    def _gnmi_path_to_string(self, path_msg) -> str:
        """Convert gNMI Path protobuf to string representation."""
        path_parts = []
        for elem in path_msg.elem:
            part = elem.name
            if elem.key:
                # Add keys in sorted order for consistency
                for key_name, key_val in sorted(elem.key.items()):
                    part += f"[{key_name}={key_val}]"
            path_parts.append(part)
        return "/".join(path_parts)
    
    # --------------------------------------------------------------#
    #  Internal loop                                                #
    # --------------------------------------------------------------#
    def _run(
        self,
        path_list: List[str],
        mode: str,
        sample_interval_ns: int,
        heartbeat_interval_ns: Optional[int],
        encoding: str,
        on_update: Optional[Callable[[dict], None]],
    ) -> None:  # pragma: no cover
        """
        Try each candidate path until the Subscribe RPC succeeds.
        * Top level mode: STREAM / ONCE / POLL  (here we always stream)
        * Per entry mode: SAMPLE / ON_CHANGE
        """
        # --- pick the correct gNMI enum strings -------------------------
        top_mode = "stream"  # explicitly stream mode
        entry_mode = mode.lower()

        for path in path_list:
            if self._stop_event.is_set():
                break

            entry: dict = {"path": path}
            LOGGER.debug("Subscription %s preparing entry for path: %s", self.sub_id, path)

            if entry_mode == "sample":
                entry["mode"]            = "sample"
                entry["sample_interval"] = sample_interval_ns
            elif entry_mode == "on_change":
                entry["mode"] = "on_change"
                if heartbeat_interval_ns:
                    entry["heartbeat_interval"] = heartbeat_interval_ns
            else:
                entry["mode"] = "target_defined"

            request = {
                "subscription": [entry],
                "mode": top_mode,
                "encoding": encoding,
            }
            LOGGER.debug("Subscription %s to be requested: %s", self.sub_id, request)
            try:
                LOGGER.debug("Sub %s attempting path %s", self.sub_id, path)
                for stream in self.gnmi_client.subscribe(request):
                    # Check if stop was requested
                    if self._stop_event.is_set():
                        LOGGER.debug("Sub %s stop requested, breaking stream loop", self.sub_id)
                        break
                    
                    LOGGER.info("Sub %s received stream message: %s", self.sub_id, stream)
                    
                    # DEBUG: Check if update has actual update messages
                    if stream.HasField("update"):
                        LOGGER.debug("Sub %s update field present, num updates: %d", 
                                   self.sub_id, len(stream.update.update))
                        if len(stream.update.update) == 0:
                            LOGGER.warning("Sub %s received update notification with NO data values - device may have no data for path %s",
                                         self.sub_id, path)
                        for i, upd in enumerate(stream.update.update):
                            LOGGER.debug("Sub %s update[%d] has val: %s, path elem count: %d", 
                                       self.sub_id, i, upd.HasField("val"), 
                                       len(upd.path.elem) if upd.path else 0)
                    
                    # Parse the protobuf message directly (like pygnmi does)
                    msg_dict = self._parse_subscribe_response(stream)
                    LOGGER.debug("Sub %s received message: %s", self.sub_id, msg_dict)
                    
                    # Process any update data
                    if msg_dict.get('update'):
                        LOGGER.debug("Sub %s got update data", self.sub_id)
                        if on_update:
                            on_update(msg_dict)
                        else:
                            self._queue.put(msg_dict)
                    # Put a dummy update if syncResponse is received to prevent timeout
                    elif msg_dict.get('sync_response'):
                        LOGGER.debug("Sub %s received sync response", self.sub_id)
                        # Optional: put a notification about the sync
                        if not on_update:
                            self._queue.put({"type": "sync_response", "value": True})
                    else:
                        LOGGER.warning("Sub %s received unknown message: %s", self.sub_id, msg_dict)

            except grpc.RpcError as err:
                # Handle graceful shutdown (channel closed)
                if err.code() == grpc.StatusCode.CANCELLED:
                    LOGGER.debug("Sub %s cancelled (channel closed) - graceful shutdown", self.sub_id)
                    break
                elif err.code() == grpc.StatusCode.INVALID_ARGUMENT:
                    LOGGER.warning("Path '%s' rejected (%s) -- trying next", path, err.details())
                    continue
                else:
                    LOGGER.exception("Subscription %s hit gRPC error: %s", self.sub_id, err)    # Change with TFS Exception
                    break

            except Exception as exc:  # pylint: disable=broad-except
                LOGGER.exception("Subscription %s failed: %s", self.sub_id, exc)        # Change with TFS Exception
                break

        LOGGER.info("Subscription thread %s terminating", self.sub_id)
