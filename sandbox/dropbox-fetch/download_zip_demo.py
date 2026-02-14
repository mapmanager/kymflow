from download_zip import CloudFolderLink

# ==========================================
# SHOWCASE SCRIPT
# ==========================================
if __name__ == "__main__":
    # PASTE YOUR LINK HERE
    # Supports Dropbox folder links or Google Drive folder links
    MY_LINK = "https://www.dropbox.com/scl/fo/imst42ttdl8urk11whh3v/AMTTnxOejgdShGttUHm4G6Q?rlkey=i16evij5gh1y3de7jgd1vv508&st=197sav5s&dl=0"

    # OPTION 1: Using a Context Manager (Recommended for Production/Render)
    # This ensures cleanup() is called even if an error occurs.
    print("--- Option 1: Context Manager ---")
    with CloudFolderLink(MY_LINK) as folder:
        paths = folder.list_all()
        print(f"Found {len(paths)} items total.")
        
        # Filter for actual files only
        files = [p for p in paths if not p.endswith('/')]
        
        if files:
            # Showcase: Get content of the very first file
            target_file = files[0]
            content = folder.get_file_content(target_file)
            print(f"Read {len(content)} bytes from '{target_file}'")


    # OPTION 2: Manual Handling (Good for interactive debugging)
    print("\n--- Option 2: Manual Handling ---")
    folder_manual = CloudFolderLink(MY_LINK)
    try:
        # Show all paths to see folder structure
        all_items = folder_manual.list_all()
        print("Recursive list of all items:")
        for item in all_items:
            print(f"  [+] {item}")
            
    finally:
        # Crucial for Render.com to free up ephemeral disk space
        folder_manual.cleanup()
        print("\nCleanup complete. Ephemeral disk space cleared.")