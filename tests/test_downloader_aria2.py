import unittest
from unittest.mock import patch, MagicMock
from downloader_aria2 import Aria2RPCBridge

class TestAria2RPCBridge(unittest.TestCase):
    def setUp(self):
        self.bridge = Aria2RPCBridge(host="localhost", port=6800, secret="mysecret")

    @patch('downloader_aria2.requests.post')
    def test_add_uri_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "some-id", "jsonrpc": "2.0", "result": "gid-1234"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        gid = self.bridge.add_uri("http://example.com/file.txt", {"dir": "/tmp"})
        self.assertEqual(gid, "gid-1234")

        # Verify the payload was sent correctly
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "http://localhost:6800/jsonrpc")
        payload = kwargs['json']
        self.assertEqual(payload['method'], "aria2.addUri")
        self.assertEqual(payload['params'][0], "token:mysecret")
        self.assertEqual(payload['params'][1], ["http://example.com/file.txt"])
        self.assertEqual(payload['params'][2], {"dir": "/tmp"})

    @patch('downloader_aria2.requests.post')
    def test_add_uri_no_secret(self, mock_post):
        bridge_no_secret = Aria2RPCBridge(host="localhost", port=6800)
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "some-id", "jsonrpc": "2.0", "result": "gid-5678"}
        mock_post.return_value = mock_response

        gid = bridge_no_secret.add_uri("http://example.com/file.txt")
        self.assertEqual(gid, "gid-5678")

        args, kwargs = mock_post.call_args
        payload = kwargs['json']
        self.assertEqual(payload['method'], "aria2.addUri")
        self.assertEqual(payload['params'][0], ["http://example.com/file.txt"])
        self.assertEqual(payload['params'][1], {})

    @patch('downloader_aria2.requests.post')
    def test_tell_status(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "id", "jsonrpc": "2.0", "result": {"status": "active"}}
        mock_post.return_value = mock_response

        status = self.bridge.tell_status("gid-1234", ["status"])
        self.assertEqual(status, {"status": "active"})

        args, kwargs = mock_post.call_args
        payload = kwargs['json']
        self.assertEqual(payload['method'], "aria2.tellStatus")
        self.assertEqual(payload['params'][1], "gid-1234")
        self.assertEqual(payload['params'][2], ["status"])

    @patch('downloader_aria2.requests.post')
    def test_remove(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "id", "jsonrpc": "2.0", "result": "gid-1234"}
        mock_post.return_value = mock_response

        res = self.bridge.remove("gid-1234")
        self.assertEqual(res, "gid-1234")

        args, kwargs = mock_post.call_args
        payload = kwargs['json']
        self.assertEqual(payload['method'], "aria2.remove")
        self.assertEqual(payload['params'][1], "gid-1234")

    @patch('downloader_aria2.requests.post')
    def test_get_version(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "id", "jsonrpc": "2.0", "result": {"version": "1.36.0", "enabledFeatures": []}}
        mock_post.return_value = mock_response

        version = self.bridge.get_version()
        self.assertEqual(version['version'], "1.36.0")

    @patch('downloader_aria2.requests.post')
    def test_rpc_error(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "id", "jsonrpc": "2.0", "error": {"code": 1, "message": "Active Download not found"}}
        mock_post.return_value = mock_response

        with self.assertRaises(ValueError) as context:
            self.bridge.tell_status("invalid-gid")

        self.assertIn("Active Download not found", str(context.exception))

    @patch('downloader_aria2.requests.post')
    def test_connection_error(self, mock_post):
        import requests
        mock_post.side_effect = requests.RequestException("Connection refused")

        with self.assertRaises(ConnectionError) as context:
            self.bridge.get_version()

        self.assertIn("Aria2 RPC Connection failed", str(context.exception))

if __name__ == '__main__':
    unittest.main()
