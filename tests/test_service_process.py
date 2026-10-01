"""The service as a real process: what a user (or the repack's own Python) actually launches."""
import http.client
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class ServiceProcessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.port = free_port()
        config = os.path.join(self.tmp.name, "dashboard.json")
        with open(config, "w") as handle:
            json.dump({"mind": {"port": self.port, "token": "sesame"}}, handle)
        env = dict(os.environ, SQUIDBOTS_DASHBOARD_JSON=config)
        # From another folder, as a scheduled task or a service would: the script must find its own package.
        self.process = subprocess.Popen([sys.executable, os.path.join(ROOT, "run-mind.py")], cwd=self.tmp.name, env=env,
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        self.addCleanup(self.stop)
        deadline = time.time() + 15
        while time.time() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=0.3):
                    return
            except OSError:
                if self.process.poll() is not None:
                    self.fail("the service exited: " + self.process.stdout.read().decode())
                time.sleep(0.1)
        self.fail("the service never listened")

    def stop(self):
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
        self.process.stdout.close()

    def request(self, method, path, body=None, token=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        connection.request(method, path, json.dumps(body) if body is not None else None, headers)
        response = connection.getresponse()
        return response.status, response.read().decode()

    def test_it_starts_from_another_folder_and_answers_health(self):
        status, body = self.request("GET", "/health")
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["ok"])

    def test_it_keeps_its_files_beside_the_config_and_writes_a_heartbeat(self):
        deadline = time.time() + 10
        beat = os.path.join(self.tmp.name, "mind-status.json")
        while time.time() < deadline and not os.path.exists(beat):
            time.sleep(0.2)
        with open(beat) as handle:
            data = json.load(handle)
        self.assertEqual((data["port"], data["pid"]), (self.port, self.process.pid))
        self.assertTrue(os.path.exists(os.path.join(self.tmp.name, "mind.sqlite")))

    def test_the_token_is_enforced_and_an_unconfigured_lane_says_so(self):
        request = {"messages": [{"role": "user", "content": "hi"}]}
        self.assertEqual(self.request("POST", "/v1/chat/completions", request)[0], 401)
        status, body = self.request("POST", "/v1/chat/completions", request, token="sesame")
        self.assertEqual(status, 503)
        self.assertIn("no LLM profile", json.loads(body)["error"]["message"])


if __name__ == "__main__":
    unittest.main()
