import aiohttp
import pytest
from aiohttp import web

from downloader_async import AsyncChunkedDownloader

# Mock aiohttp server for testing

async def handle_get(request):
    data = b"a" * 5000

    range_header = request.headers.get('Range')
    if range_header:
        # e.g., bytes=0-999
        parts = range_header.replace('bytes=', '').split('-')
        start = int(parts[0])
        end = int(parts[1]) if parts[1] else len(data) - 1

        chunk = data[start:end+1]

        headers = {
            'Content-Range': f'bytes {start}-{end}/{len(data)}',
            'Accept-Ranges': 'bytes'
        }
        return web.Response(body=chunk, status=206, headers=headers)

    return web.Response(body=data, headers={'Content-Length': str(len(data))})

async def handle_head(request):
    headers = {
        'Content-Length': '5000',
        'Accept-Ranges': 'bytes'
    }
    return web.Response(status=200, headers=headers)

# For testing fallback
async def handle_no_size_get(request):
    data = b"b" * 2000
    return web.Response(body=data)

async def handle_no_size_head(request):
    return web.Response(status=200)

# For testing retries
request_counts = {}

async def handle_flaky_get(request):
    global request_counts
    range_header = request.headers.get('Range')

    if not range_header:
        data = b"c" * 3000
        return web.Response(body=data, headers={'Content-Length': '3000'})

    if range_header not in request_counts:
        request_counts[range_header] = 0
    request_counts[range_header] += 1

    # Fail first 2 times for each chunk
    if request_counts[range_header] <= 2:
        return web.Response(status=500)

    data = b"c" * 3000
    parts = range_header.replace('bytes=', '').split('-')
    start = int(parts[0])
    end = int(parts[1]) if parts[1] else len(data) - 1
    chunk = data[start:end+1]

    headers = {
        'Content-Range': f'bytes {start}-{end}/{len(data)}',
        'Accept-Ranges': 'bytes'
    }
    return web.Response(body=chunk, status=206, headers=headers)

async def handle_flaky_head(request):
    headers = {
        'Content-Length': '3000',
        'Accept-Ranges': 'bytes'
    }
    return web.Response(status=200, headers=headers)

import pytest_asyncio


@pytest_asyncio.fixture
async def aiohttp_server_mock(aiohttp_server):
    app = web.Application()
    # In newer aiohttp, add_get automatically adds HEAD if it's the same handler,
    # but here we use different handlers so we should just use route() directly
    app.router.add_route('GET', '/test', handle_get)
    app.router.add_route('HEAD', '/test', handle_head)

    app.router.add_route('GET', '/no_size', handle_no_size_get)
    app.router.add_route('HEAD', '/no_size', handle_no_size_head)

    app.router.add_route('GET', '/flaky', handle_flaky_get)
    app.router.add_route('HEAD', '/flaky', handle_flaky_head)

    return await aiohttp_server(app)

@pytest.mark.asyncio
async def test_async_chunked_downloader_basic(aiohttp_server_mock, tmp_path):
    url = f"http://{aiohttp_server_mock.host}:{aiohttp_server_mock.port}/test"
    output_file = tmp_path / "downloaded.bin"

    downloader = AsyncChunkedDownloader(url, str(output_file), chunk_size=1000)
    await downloader.download()

    assert output_file.exists()
    assert output_file.read_bytes() == b"a" * 5000

@pytest.mark.asyncio
async def test_async_chunked_downloader_no_size(aiohttp_server_mock, tmp_path):
    url = f"http://{aiohttp_server_mock.host}:{aiohttp_server_mock.port}/no_size"
    output_file = tmp_path / "downloaded_no_size.bin"

    downloader = AsyncChunkedDownloader(url, str(output_file), chunk_size=1000)
    await downloader.download()

    assert output_file.exists()
    assert output_file.read_bytes() == b"b" * 2000

@pytest.mark.asyncio
async def test_async_chunked_downloader_retry(aiohttp_server_mock, tmp_path):
    # Reset counts
    global request_counts
    request_counts.clear()

    url = f"http://{aiohttp_server_mock.host}:{aiohttp_server_mock.port}/flaky"
    output_file = tmp_path / "downloaded_flaky.bin"

    # We set max_retries to 3. The server fails the first 2 times, so it should succeed on the 3rd attempt
    downloader = AsyncChunkedDownloader(url, str(output_file), chunk_size=1000, max_retries=3)
    await downloader.download()

    assert output_file.exists()
    assert output_file.read_bytes() == b"c" * 3000

@pytest.mark.asyncio
async def test_async_chunked_downloader_retry_failure(aiohttp_server_mock, tmp_path):
    # Reset counts
    global request_counts
    request_counts.clear()

    url = f"http://{aiohttp_server_mock.host}:{aiohttp_server_mock.port}/flaky"
    output_file = tmp_path / "downloaded_fail.bin"

    # Max retries = 2, server fails first 2 times. Should raise an exception.
    downloader = AsyncChunkedDownloader(url, str(output_file), chunk_size=1000, max_retries=2)

    with pytest.raises(aiohttp.ClientResponseError) as excinfo:
        await downloader.download()

    assert excinfo.value.status == 500
