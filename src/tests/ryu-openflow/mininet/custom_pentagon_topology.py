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


import json, logging, socketserver, threading, time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import RemoteController
#from mininet.cli import CLI
from mininet.link import TCLink

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

class PentagonTopo(Topo):
    def build(self):
        sw1 = self.addSwitch('s1')
        sw2 = self.addSwitch('s2')
        sw3 = self.addSwitch('s3')
        sw4 = self.addSwitch('s4')
        sw5 = self.addSwitch('s5')

        h1 = self.addHost('h1', ip='10.0.0.1', mac='00:00:00:00:00:01')
        h2 = self.addHost('h2', ip='10.0.0.2', mac='00:00:00:00:00:02')
        h3 = self.addHost('h3', ip='10.0.0.3', mac='00:00:00:00:00:03')
        h4 = self.addHost('h4', ip='10.0.0.4', mac='00:00:00:00:00:04')

        self.addLink(sw1, sw2)
        self.addLink(sw2, sw3)
        self.addLink(sw3, sw4)
        self.addLink(sw4, sw5)
        self.addLink(sw5, sw1)

        self.addLink(h1, sw2)
        self.addLink(h2, sw2)
        self.addLink(h3, sw5)
        self.addLink(h4, sw5)


def build_ping_handler(net: Mininet):
    """
    Create a HTTP request handler that performs pings between hosts.
    """
    class PingHandler(BaseHTTPRequestHandler):
        #def log_message(self, *args, **kwargs):
        #    # Silence default stdout logging.
        #    return

        def _send_json(self, status: int, payload: dict):
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path != '/ping':
                self._send_json(404, {'error': 'not found'})
                return

            params = parse_qs(parsed.query)
            source = params.get('source', [None])[0]
            target = params.get('target', [None])[0]
            count_val = params.get('count', ['3'])[0]

            if not source or not target:
                self._send_json(400, {
                    'error': 'source and target query parameters are required',
                    'params': str(params),
                })
                return

            count = None
            try:
                count = int(count_val)
                if count <= 0:
                    raise ValueError()
            except ValueError:
                self._send_json(400, {
                    'error': 'count must be a positive integer',
                    'params': str(params),
                })
                return

            src_host = None
            dst_host = None
            try:
                src_host = net.get(source)
                dst_host = net.get(target)
            except KeyError as exc:
                self._send_json(404, {
                    'error': f'Unknown host: {exc}',
                    'params': str(params),
                })
                return
            
            destination_ip = dst_host.IP()
            output = src_host.cmd(f'ping -c {count} {destination_ip}')

            self._send_json(200, {
                'source': source,
                'target': target,
                'destination_ip': destination_ip,
                'count': count,
                'output': output,
            })

    return PingHandler


class ThreadingHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True

if __name__ == '__main__':
    topo = PentagonTopo()
    ctrl = RemoteController('ryu', ip='172.254.252.10', port=6653)
    net = Mininet(
        topo=topo,
        controller=ctrl,
        link=TCLink
    )

    net.start()
    net.staticArp()

    ping_handler = build_ping_handler(net)
    http_server = ThreadingHTTPServer(('0.0.0.0', 5000), ping_handler)
    server_thread = threading.Thread(target=http_server.serve_forever, daemon=True)
    server_thread.start()

    print('Custom Pentagon Topology is up with static ARP.')
    print('HTTP ping server running at http://0.0.0.0:5000/ping?source=h1&target=h2&count=3')

    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print('Stopping Mininet...')
        http_server.shutdown()
        http_server.server_close()
        net.stop()
