import os
import unittest
from unittest.mock import MagicMock, patch

from batch_downloader import BatchDownloader


class TestBatchDownloader(unittest.TestCase):
    def setUp(self):
        self.downloader = BatchDownloader(num_workers=2)

    @patch('builtins.open', new_callable=unittest.mock.mock_open, read_data="http://example.com/file1.jpg\nhttp://example.com/file2.jpg\n\n")
    @patch('os.path.exists', return_value=True)
    def test_read_urls(self, mock_exists, mock_file):
        urls = self.downloader.read_urls('dummy.txt')
        self.assertEqual(len(urls), 2)
        self.assertEqual(urls[0], "http://example.com/file1.jpg")
        self.assertEqual(urls[1], "http://example.com/file2.jpg")

    def test_read_urls_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            self.downloader.read_urls('nonexistent.txt')

    @patch('batch_downloader.requests.get')
    def test_download_item_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.iter_content.return_value = [b"data chunk"]
        mock_get.return_value = mock_response

        with patch('builtins.open', unittest.mock.mock_open()) as mock_file:
            self.downloader.download_item("http://example.com/image.jpg", "/tmp")
            mock_get.assert_called_once_with("http://example.com/image.jpg", stream=True, timeout=10)
            mock_response.raise_for_status.assert_called_once()
            mock_file.assert_called_once_with(os.path.join("/tmp", "image.jpg"), 'wb')
            mock_file().writelines.assert_called_with([b"data chunk"])

    @patch('batch_downloader.requests.get')
    def test_download_item_failure(self, mock_get):
        mock_get.side_effect = Exception("Network Error")

        with self.assertRaises(Exception) as context:
            self.downloader.download_item("http://example.com/bad.jpg", "/tmp")

        self.assertTrue("Network Error" in str(context.exception))

    @patch('batch_downloader.BatchDownloader.download_item')
    @patch('batch_downloader.BatchDownloader.read_urls')
    @patch('batch_downloader.BatchDownloader.print_summary')
    @patch('os.makedirs')
    def test_process_batch_success_and_failure(self, mock_makedirs, mock_print, mock_read_urls, mock_download_item):
        mock_read_urls.return_value = [
            "http://example.com/good1.jpg",
            "http://example.com/bad.jpg",
            "http://example.com/good2.jpg"
        ]

        def side_effect_download(url, dest_dir):
            if "bad" in url:
                raise RuntimeError("Simulated Failure")

        mock_download_item.side_effect = side_effect_download

        stats = self.downloader.process_batch('dummy.txt', '/tmp')

        self.assertEqual(stats['total'], 3)
        self.assertEqual(stats['success'], 2)
        self.assertEqual(stats['failed'], 1)

        mock_makedirs.assert_called_once_with('/tmp', exist_ok=True)
        self.assertEqual(mock_download_item.call_count, 3)
        mock_print.assert_called_once()

if __name__ == '__main__':
    unittest.main()
