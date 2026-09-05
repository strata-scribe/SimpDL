import os
import tempfile
from unittest import mock
from unittest.mock import MagicMock, patch

import pytest
import requests
import requests_mock

from downloader import download_image_with_retry


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


@pytest.fixture
def mock_session():
    session = requests.Session()
    return session


@patch("time.sleep", return_value=None)
def test_download_image_with_retry_timeout(mock_sleep, mock_session, tmp_path):
    img_url = "http://test.com/image.jpg"
    filepath = str(tmp_path / "image.jpg")
    headers = {}
    mock_log = MagicMock()

    with requests_mock.Mocker() as m:
        m.get(img_url, exc=requests.exceptions.Timeout("Connection timed out"))

        result = download_image_with_retry(mock_session, img_url, filepath, headers, mock_log, max_retries=3)

        assert result is False
        assert mock_sleep.call_count == 3
        # Should backoff exponentially: 2**0, 2**1, 2**2
        assert mock_sleep.call_args_list[0][0][0] == 1
        assert mock_sleep.call_args_list[1][0][0] == 2
        assert mock_sleep.call_args_list[2][0][0] == 4


@patch("time.sleep", return_value=None)
def test_download_image_with_retry_403(mock_sleep, mock_session, tmp_path):
    img_url = "http://test.com/image.jpg"
    filepath = str(tmp_path / "image.jpg")
    headers = {}
    mock_log = MagicMock()

    with requests_mock.Mocker() as m:
        m.get(img_url, status_code=403)

        result = download_image_with_retry(mock_session, img_url, filepath, headers, mock_log, max_retries=3)

        assert result is False
        assert mock_sleep.call_count == 0


def test_download_image_with_retry_insufficient_disk_space(mock_session, tmp_path):
    img_url = "http://test.com/image.jpg"
    filepath = str(tmp_path / "image.jpg")
    headers = {}
    mock_log = MagicMock()

    with requests_mock.Mocker() as m:
        m.get(img_url, content=b"test data", status_code=200)

        # Mock open to raise OSError with ENOSPC
        with patch("builtins.open", side_effect=OSError(28, "No space left on device")):
            with pytest.raises(OSError) as excinfo:
                download_image_with_retry(mock_session, img_url, filepath, headers, mock_log, max_retries=3)

            assert "No space left on device" in str(excinfo.value)
