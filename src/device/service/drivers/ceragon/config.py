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
Connection settings for one Ceragon device
==========================================
Built from the TeraFlowSDN device's ``_connect/address``, ``_connect/port`` and
``_connect/settings``. There are no lab defaults: address and port always come
from the device record.

Recognised ``_connect/settings`` keys:
  username, password      RESTCONF credentials (default admin / admin)
  scheme                  "http" or "https" (default http; ports 443/8443 imply https)
  verify_tls              verify the device certificate (default true)
  timeout                 request timeout in seconds (default 15)
  model                   optional product hint, e.g. "IP-50C" or "EH-8010FX"
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


def _as_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


@dataclass
class CeragonClientConfig:
    """Connectivity parameters for one Ceragon RESTCONF endpoint."""

    device_ip: str
    device_port: int = 80
    username: str = "admin"
    password: str = "admin"
    use_https: bool = False
    verify_tls: bool = True
    timeout_seconds: int = 15
    model_hint: Optional[str] = None

    @property
    def ceragon_base_url(self) -> str:
        scheme = "https" if self.use_https or self.device_port in (443, 8443) else "http"
        port = 443 if (scheme == "https" and self.device_port == 80) else self.device_port
        return f"{scheme}://{self.device_ip}:{port}"

    @classmethod
    def from_tfs_settings(cls, address: str, port: int, settings: Dict[str, Any]) -> "CeragonClientConfig":
        settings = settings or {}
        return cls(
            device_ip=str(address),
            device_port=int(port),
            username=str(settings.get("username", "admin")),
            password=str(settings.get("password", "admin")),
            use_https=str(settings.get("scheme", "http")).lower() == "https",
            verify_tls=_as_bool(settings.get("verify_tls"), True),
            timeout_seconds=int(settings.get("timeout", 15)),
            model_hint=settings.get("model") or None,
        )
