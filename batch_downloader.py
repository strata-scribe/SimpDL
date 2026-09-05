import os
import queue
import threading
from urllib.parse import urlparse
import requests

class BatchDownloader:
    def __init__(self, num_workers=4):
        self.num_workers = num_workers
        self.queue = queue.Queue()
        self.stats = {'total': 0, 'success': 0, 'failed': 0}
        self.stats_lock = threading.Lock()

    def read_urls(self, file_path):
        """Read URLs from a text file, ignoring empty lines."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"URL file not found: {file_path}")

        urls = []
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                url = line.strip()
                if url:
                    urls.append(url)
        return urls

    def download_item(self, url, dest_dir):
        """Download a single URL and save to dest_dir."""
        parsed = urlparse(url)
        filename = os.path.basename(parsed.path)
        if not filename:
            filename = "index.html"

        dest_path = os.path.join(dest_dir, filename)

        response = requests.get(url, stream=True, timeout=10)
        response.raise_for_status()

        with open(dest_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

    def worker(self, dest_dir):
        """Worker thread to process items from the queue."""
        while True:
            try:
                url = self.queue.get_nowait()
            except queue.Empty:
                break

            try:
                self.download_item(url, dest_dir)
                with self.stats_lock:
                    self.stats['success'] += 1
            except Exception as e:
                with self.stats_lock:
                    self.stats['failed'] += 1
                print(f"Failed to download {url}: {e}")
            finally:
                self.queue.task_done()

    def print_summary(self):
        """Print the summary stats of the batch download."""
        print("\n--- Summary Stats ---")
        print(f"Total URLs: {self.stats['total']}")
        print(f"Successful: {self.stats['success']}")
        print(f"Failed:     {self.stats['failed']}")
        print("---------------------\n")

    def process_batch(self, file_path, dest_dir):
        """Read URLs, queue items, start workers, and print summary."""
        os.makedirs(dest_dir, exist_ok=True)

        urls = self.read_urls(file_path)
        self.stats['total'] = len(urls)
        self.stats['success'] = 0
        self.stats['failed'] = 0

        for url in urls:
            self.queue.put(url)

        threads = []
        for _ in range(self.num_workers):
            t = threading.Thread(target=self.worker, args=(dest_dir,))
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        self.print_summary()
        return self.stats
