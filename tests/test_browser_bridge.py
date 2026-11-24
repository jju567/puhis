import json
import threading
import unittest
import urllib.error
import urllib.request

from puhis.stt.browser_bridge import BrowserSpeechBridge


class BrowserBridgeTests(unittest.TestCase):
    def test_bridge_serves_html_and_forwards_posted_candidates(self) -> None:
        received: list[list[str]] = []
        statuses: list[str] = []
        got_event = threading.Event()
        status_event = threading.Event()

        def on_candidates(cands: list[str]) -> None:
            received.append(cands)
            got_event.set()

        def on_status(state: str) -> None:
            statuses.append(state)
            status_event.set()

        bridge = BrowserSpeechBridge(on_candidates=on_candidates, on_status=on_status)
        url = bridge.start()
        try:
            with urllib.request.urlopen(url, timeout=3.0) as resp:
                self.assertEqual(resp.status, 200)
                html = resp.read().decode("utf-8")
                self.assertIn("SpeechRecognition", html)

            with urllib.request.urlopen(url + "ping", timeout=3.0) as ping_resp:
                self.assertEqual(ping_resp.status, 200)

            status_req = urllib.request.Request(
                url + "status",
                data=json.dumps({"state": "listening"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(status_req, timeout=3.0) as status_resp:
                self.assertEqual(status_resp.status, 200)

            self.assertTrue(status_event.wait(timeout=2.0))
            self.assertEqual(statuses, ["listening"])

            payload = json.dumps({"candidates": ["puhis save t1", "puhis save d1"]}).encode("utf-8")
            req = urllib.request.Request(
                url + "utterance",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=3.0) as post_resp:
                self.assertEqual(post_resp.status, 200)

            self.assertTrue(got_event.wait(timeout=2.0))
            self.assertEqual(received, [["puhis save t1", "puhis save d1"]])
        finally:
            bridge.stop()

        self.assertFalse(bridge.is_running)

    def test_bridge_rejects_invalid_json_with_bad_request(self) -> None:
        bridge = BrowserSpeechBridge(on_candidates=lambda _c: None)
        url = bridge.start()
        try:
            req = urllib.request.Request(
                url + "utterance",
                data=b"{ei json",
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(req, timeout=3.0)
            self.assertEqual(ctx.exception.code, 400)
        finally:
            bridge.stop()


if __name__ == "__main__":
    unittest.main()
