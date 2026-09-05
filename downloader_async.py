import asyncio
import logging

import aiohttp


class AsyncChunkedDownloader:
    """
    An asynchronous chunked file downloader using aiohttp.
    Features:
      - Connection pooling
      - Range requests (chunked downloading)
      - Retry backoff
    """
    def __init__(self, url, output_path, chunk_size=1024*1024, max_connections=5, max_retries=3, headers=None):
        self.url = url
        self.output_path = output_path
        self.chunk_size = chunk_size
        self.max_connections = max_connections
        self.max_retries = max_retries
        self.headers = headers or {}
        # Ensure we do not request compressed data that could break range parsing,
        # unless handled explicitly.
        self.headers.setdefault("Accept-Encoding", "identity")
        self._lock = asyncio.Lock()
        self.logger = logging.getLogger(__name__)

    async def get_file_size(self, session: aiohttp.ClientSession) -> int:
        """
        Attempts to find the total size of the file to download.
        """
        # 1. Try HEAD request
        try:
            async with session.head(self.url, allow_redirects=True, headers=self.headers) as response:
                if response.status == 200:
                    size = response.headers.get("Content-Length")
                    if size:
                        return int(size)
        except Exception as e:
            self.logger.debug(f"HEAD request failed to get size: {e}")

        # 2. Try GET with Range bytes=0-0
        try:
            headers = {**self.headers, "Range": "bytes=0-0"}
            async with session.get(self.url, headers=headers) as response:
                if response.status == 206:
                    cr = response.headers.get("Content-Range")
                    if cr and "/" in cr:
                        return int(cr.split("/")[-1])
                # If we requested 0-0 and got 200, it means the server ignores Range headers,
                # but it might have sent us the full file length.
                elif response.status == 200:
                    # In this case, we can't reliably do range requests, but we might know the size.
                    # Returning 0 forces fallback to single connection download which is correct
                    # when the server doesn't support ranges.
                    return 0
        except Exception as e:
            self.logger.debug(f"GET Range 0-0 request failed to get size: {e}")

        return 0

    async def download_chunk(self, session: aiohttp.ClientSession, start: int, end: int, file_obj):
        """
        Downloads a specific byte range of the file. Includes retry logic with exponential backoff.
        """
        headers = {**self.headers, "Range": f"bytes={start}-{end}"}

        for attempt in range(self.max_retries):
            try:
                # Add reasonable timeout per chunk
                async with session.get(self.url, headers=headers, timeout=aiohttp.ClientTimeout(total=60)) as response:
                    response.raise_for_status()
                    data = await response.read()

                    async with self._lock:
                        file_obj.seek(start)
                        file_obj.write(data)
                    return
            except Exception as e:
                self.logger.warning(f"Chunk {start}-{end} attempt {attempt + 1} failed: {e}")
                if attempt == self.max_retries - 1:
                    raise
                # Exponential backoff
                await asyncio.sleep(2 ** attempt)

    async def download(self):
        """
        Main entry point for downloading the file.
        Will fallback to normal non-chunked download if file size cannot be determined.
        """
        connector = aiohttp.TCPConnector(limit=self.max_connections)
        async with aiohttp.ClientSession(connector=connector) as session:
            file_size = await self.get_file_size(session)

            if file_size == 0:
                self.logger.info("File size could not be determined. Falling back to simple download.")
                # Fallback to normal download without range requests
                async with session.get(self.url, headers=self.headers) as response:
                    response.raise_for_status()
                    data = await response.read()
                    with open(self.output_path, "wb") as f:  # noqa: ASYNC230
                        f.write(data)
                return

            self.logger.info(f"Downloading {file_size} bytes in chunks of {self.chunk_size} bytes.")

            # Pre-allocate the file
            with open(self.output_path, "wb") as file_obj:  # noqa: ASYNC230
                file_obj.seek(file_size - 1)
                file_obj.write(b'\0')

            # Open file for read/write
            with open(self.output_path, "rb+") as file_obj:  # noqa: ASYNC230
                tasks = []
                for start in range(0, file_size, self.chunk_size):
                    end = min(start + self.chunk_size - 1, file_size - 1)
                    tasks.append(self.download_chunk(session, start, end, file_obj))

                # Execute chunk downloads concurrently
                await asyncio.gather(*tasks)
