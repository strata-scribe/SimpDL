import logging
import uuid

import requests


class Aria2RPCBridge:
    """
    An aria2c RPC bridge allowing multi-connection accelerated downloading
    as an alternative to native HTTP requests.
    """
    def __init__(self, host="localhost", port=6800, secret=None):
        self.host = host
        self.port = port
        self.secret = secret
        self.rpc_url = f"http://{host}:{port}/jsonrpc"
        self.logger = logging.getLogger(__name__)

    def _make_payload(self, method, *params):
        call_params = []
        if self.secret:
            call_params.append(f"token:{self.secret}")
        call_params.extend(params)

        return {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": method,
            "params": call_params
        }

    def _call(self, method, *params):
        payload = self._make_payload(method, *params)
        try:
            response = requests.post(self.rpc_url, json=payload, timeout=10)
            response.raise_for_status()
            data = response.json()
            if "error" in data:
                error_msg = data['error'].get('message', 'Unknown Error')
                raise ValueError(error_msg)
            return data.get("result")
        except requests.RequestException as e:
            self.logger.exception("Failed to connect to Aria2 RPC")
            raise ConnectionError("Aria2 RPC Connection failed") from e

    def add_uri(self, urls, options=None):
        """
        Adds a new download.
        :param urls: A list of URIs or a single URI string.
        :param options: A dictionary of aria2c options (e.g., {'dir': '/path', 'out': 'file.ext'})
        :return: GID of the newly registered download.
        """
        if isinstance(urls, str):
            urls = [urls]
        if options is None:
            options = {}
        return self._call("aria2.addUri", urls, options)

    def tell_status(self, gid, keys=None):
        """
        Returns the status of a download.
        :param gid: The GID of the download.
        :param keys: A list of keys to return (e.g., ['status', 'totalLength', 'completedLength'])
        :return: A dictionary of status information.
        """
        if keys:
            return self._call("aria2.tellStatus", gid, keys)
        return self._call("aria2.tellStatus", gid)

    def remove(self, gid):
        """
        Removes a download.
        """
        return self._call("aria2.remove", gid)

    def get_version(self):
        """
        Returns the version of aria2 and the list of enabled features.
        """
        return self._call("aria2.getVersion")
