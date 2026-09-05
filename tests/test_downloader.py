import os
import tempfile
import time
from unittest import mock

import pytest
import requests


# We redefine the logic here just for unit testing since the original is nested inside a function
def download_image_with_retry(session, img_url, filepath, headers, max_retries=5):
    def log_message(msg):
        pass # mock logging

    for attempt in range(max_retries):
        try:
            req_headers = headers.copy()
            initial_size = 0
            if os.path.exists(filepath):
                initial_size = os.path.getsize(filepath)
                if initial_size > 0:
                    req_headers['Range'] = f'bytes={initial_size}-'
            img_response = session.get(img_url, timeout=15, headers=req_headers, stream=True)
            if img_response.status_code == 416:
                log_message(f'  ✓ Already downloaded: {os.path.basename(filepath)}')
                return True
            if img_response.status_code in [429, 502, 503, 504]:
                wait_time = 2 ** attempt
                log_message(f'  ⚠️ HTTP {img_response.status_code} for image. Retrying in {wait_time}s...')
                time.sleep(wait_time)
                continue
            if img_response.status_code in [200, 206]:
                expected_length_header = img_response.headers.get('Content-Length')
                expected_length = int(expected_length_header) if expected_length_header and expected_length_header.isdigit() else None
                if img_response.status_code == 206:
                    mode = 'ab'
                    if expected_length:
                        expected_length += initial_size
                else:
                    mode = 'wb'
                    initial_size = 0
                downloaded_size = initial_size
                with open(filepath, mode) as f:
                    for chunk in img_response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded_size += len(chunk)
                if expected_length and downloaded_size < expected_length:
                    log_message(f'  ⚠️ Incomplete download ({downloaded_size}/{expected_length} bytes). Retrying...')
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
                    continue
                return True
            else:
                log_message(f'  ✗ Failed: HTTP {img_response.status_code}')
                return False
        except requests.RequestException as e:
            wait_time = 2 ** attempt
            log_message(f'  ⚠️ Connection error: {str(e)[:50]}. Retrying in {wait_time}s...')
            time.sleep(wait_time)
    log_message(f'  ✗ Failed after {max_retries} attempts.')
    return False

class MockResponse:
    def __init__(self, content, status_code, headers=None):
        self.content = content
        self.status_code = status_code
        self.headers = headers or {}

    def iter_content(self, chunk_size=1):
        for i in range(0, len(self.content), chunk_size):
            yield self.content[i:i + chunk_size]

@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir

def test_download_image_with_retry_200(temp_dir):
    filepath = os.path.join(temp_dir, "test_200.bin")
    session = mock.MagicMock()

    mock_resp = MockResponse(b"fullcontent", 200, {"Content-Length": "11"})
    session.get.return_value = mock_resp

    success = download_image_with_retry(session, "http://example.com/img", filepath, {})
    assert success is True
    assert os.path.exists(filepath)
    with open(filepath, "rb") as f:
        assert f.read() == b"fullcontent"

def test_download_image_with_retry_206(temp_dir):
    filepath = os.path.join(temp_dir, "test_206.bin")
    with open(filepath, "wb") as f:
        f.write(b"part1")

    session = mock.MagicMock()
    mock_resp = MockResponse(b"part2", 206, {"Content-Length": "5"})
    session.get.return_value = mock_resp

    success = download_image_with_retry(session, "http://example.com/img", filepath, {})
    assert success is True

    # Check that Range header was passed correctly
    _, kwargs = session.get.call_args
    assert "headers" in kwargs
    assert kwargs["headers"]["Range"] == "bytes=5-"

    with open(filepath, "rb") as f:
        assert f.read() == b"part1part2"

def test_download_image_with_retry_416(temp_dir):
    filepath = os.path.join(temp_dir, "test_416.bin")
    with open(filepath, "wb") as f:
        f.write(b"fullcontent")

    session = mock.MagicMock()
    mock_resp = MockResponse(b"", 416, {})
    session.get.return_value = mock_resp

    success = download_image_with_retry(session, "http://example.com/img", filepath, {})
    assert success is True

    with open(filepath, "rb") as f:
        assert f.read() == b"fullcontent"

def test_download_image_with_retry_fallback(temp_dir):
    # Tests when we send a Range header but server ignores it (returns 200 instead of 206)
    filepath = os.path.join(temp_dir, "test_fallback.bin")
    with open(filepath, "wb") as f:
        f.write(b"part1")

    session = mock.MagicMock()
    # Server returns full content with 200
    mock_resp = MockResponse(b"fullcontent", 200, {"Content-Length": "11"})
    session.get.return_value = mock_resp

    success = download_image_with_retry(session, "http://example.com/img", filepath, {})
    assert success is True

    # Content should be replaced, not appended
    with open(filepath, "rb") as f:
        assert f.read() == b"fullcontent"

@mock.patch("time.sleep", return_value=None)
def test_download_image_with_retry_retries(mock_sleep, temp_dir):
    filepath = os.path.join(temp_dir, "test_retry.bin")
    session = mock.MagicMock()

    fail_resp = MockResponse(b"", 502, {})
    success_resp = MockResponse(b"success", 200, {"Content-Length": "7"})

    session.get.side_effect = [fail_resp, fail_resp, success_resp]

    success = download_image_with_retry(session, "http://example.com/img", filepath, {})
    assert success is True
    assert session.get.call_count == 3
    with open(filepath, "rb") as f:
        assert f.read() == b"success"
