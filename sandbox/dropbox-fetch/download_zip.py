import os
import shutil
import tempfile
import zipfile
import time
from typing import List, Optional
import requests
import gdown

class CloudFolderLink:
    """High-level interface for Dropbox and Google Drive public folders.
    
    Includes progress logging for long-running ZIP generation and downloads.
    """

    def __init__(self, shared_url: str):
        """Initializes with a public folder URL."""
        self.url: str = shared_url
        self._temp_dir: str = tempfile.mkdtemp()
        self._zip_path: str = os.path.join(self._temp_dir, "folder.zip")
        self._zip_handle: Optional[zipfile.ZipFile] = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

    def _is_gdrive(self) -> bool:
        return "drive.google.com" in self.url

    def _get_dropbox_download_url(self) -> str:
        if "dl=0" in self.url:
            return self.url.replace("dl=0", "dl=1")
        return f"{self.url}&dl=1" if "?" in self.url else f"{self.url}?dl=1"

    def _download_to_disk(self) -> None:
        """Downloads folder to disk with progress prints."""
        if self._zip_handle is not None:
            return

        print(f"[LOG] Target identified as: {'Google Drive' if self._is_gdrive() else 'Dropbox'}")

        if self._is_gdrive():
            print("[LOG] Starting gdown folder download (this may take a moment)...")
            downloaded_path = os.path.join(self._temp_dir, "gdrive_content")
            gdown.download_folder(url=self.url, output=downloaded_path, quiet=False)
            print("[LOG] Zipping GDrive content for consistent API access...")
            shutil.make_archive(self._zip_path.replace('.zip', ''), 'zip', downloaded_path)
        else:
            # Dropbox logic
            dl_url = self._get_dropbox_download_url()
            print(f"[LOG] Requesting ZIP from Dropbox. Waiting for server to bundle 2000+ items...")
            
            start_time = time.time()
            with requests.get(dl_url, stream=True) as r:
                r.raise_for_status()
                print(f"[LOG] Connection established in {time.time() - start_time:.2f}s. Streaming data...")
                
                total_size = int(r.headers.get('content-length', 0))
                downloaded = 0
                
                with open(self._zip_path, 'wb') as f:
                    # Stream in 1MB chunks to track progress
                    for chunk in r.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0:
                                percent = (downloaded / total_size) * 100
                                print(f"    Progress: {percent:.1f}% ({downloaded / 1024 / 1024:.1f} MB)", end='\r')
                            else:
                                print(f"    Received: {downloaded / 1024 / 1024:.1f} MB...", end='\r')
            print(f"\n[LOG] Download complete. Total size: {os.path.getsize(self._zip_path) / 1024 / 1024:.2f} MB")
        
        self._zip_handle = zipfile.ZipFile(self._zip_path, 'r')

    def list_all(self) -> List[str]:
        """Lists all files and folders recursively."""
        self._download_to_disk()
        return self._zip_handle.namelist() if self._zip_handle else []

    def get_file_content(self, path: str) -> bytes:
        """Fetches raw bytes for a specific file path."""
        self._download_to_disk()
        if not self._zip_handle:
            return b""
        with self._zip_handle.open(path) as f:
            return f.read()

    def cleanup(self) -> None:
        """Deletes temporary files and closes ZIP handles."""
        if self._zip_handle:
            self._zip_handle.close()
            self._zip_handle = None
        if os.path.exists(self._temp_dir):
            shutil.rmtree(self._temp_dir)

# ==========================================
# SHOWCASE SCRIPT
# ==========================================
if __name__ == "__main__":
    TEST_LINK = "https://www.dropbox.com/scl/fo/imst42ttdl8urk11whh3v/AMTTnxOejgdShGttUHm4G6Q?rlkey=i16evij5gh1y3de7jgd1vv508&st=197sav5s&dl=0"

    print("--- STARTING CLOUD FETCH ---")
    try:
        with CloudFolderLink(TEST_LINK) as folder:
            items = folder.list_all()
            print(f"[LOG] Successfully indexed {len(items)} items.")
            
            files_only = [p for p in items if not p.endswith('/')]
            if files_only:
                # Test reading a specific file from your folder
                test_file = files_only[0] 
                print(f"[LOG] Testing file read for: {test_file}")
                data = folder.get_file_content(test_file)
                print(f"[SUCCESS] Read {len(data)} bytes.")

    except Exception as e:
        print(f"\n[ERROR] An error occurred: {e}")
    
    print("\n--- PROCESS COMPLETE ---")

# ==========================================
# SHOWCASE SCRIPT
# ==========================================
if __name__ == "__main__":
    # 1. Replace with your actual Dropbox or Google Drive folder link
    
    # big, all dates for one condition
    TEST_LINK = "https://www.dropbox.com/scl/fo/imst42ttdl8urk11whh3v/AMTTnxOejgdShGttUHm4G6Q?rlkey=i16evij5gh1y3de7jgd1vv508&st=197sav5s&dl=0"

    # smaller, just one date (a number of tif and txt)
    TEST_LINK = "https://www.dropbox.com/scl/fo/nyz3wkefza06gi43on76d/ABt0cLUck2I8TKyIlaLRwns?rlkey=b46cfxywxa4o8i0jxreagaq3i&st=c7l6oa4w&dl=0"

    print("--- SHOWCASE: CloudFolderLink ---")

    # OPTION 1: Automatic Cleanup (Recommended)
    # The 'with' statement now works because __enter__ and __exit__ are defined.
    with CloudFolderLink(TEST_LINK) as folder:
        items = folder.list_all()
        print(f"Total objects found: {len(items)}")
        
        # Showcase: Reading the content of a specific file
        files_only = [p for p in items if not p.endswith('/')]
        if files_only:
            file_to_read = files_only[0]
            data = folder.get_file_content(file_to_read)
            print(f"Successfully read {len(data)} bytes from: {file_to_read}")

    print("\n--- Cleanup verified: Disk space released. ---")
