import os
import sqlite3
import uuid
import hashlib
import shutil
import json
import exifread
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

# --- CONFIGURATION ---
BASE_DIR = os.getcwd()
IMPORT_DIR = os.path.join(BASE_DIR, "import")
IN_PROGRESS_DIR = os.path.join(BASE_DIR, "in_progress")
DUPLICATES_DIR = os.path.join(BASE_DIR, "duplicates")
DB_PATH = os.path.join(BASE_DIR, "duplicate_check.sqlite")

db_lock = Lock()

def get_file_hash(file_path):
    hasher = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()

def get_exif_data(file_path):
    """Extracts EXIF data and converts tags to string for JSON compatibility."""
    with open(file_path, 'rb') as f:
        tags = exifread.process_file(f, details=False)
    
    # Convert tag values to strings because some EXIF types aren't JSON serializable
    return {str(tag): str(val) for tag, val in tags.items()}

def process_file(file_info):
    main_folder, sub_folder, filename, source_path = file_info
    
    file_uuid = str(uuid.uuid4())
    file_hash = get_file_hash(source_path)
    run_timestamp = datetime.now().isoformat()
    
    # 1. Prepare In-Progress Path
    work_dir = os.path.join(IN_PROGRESS_DIR, main_folder, sub_folder, file_uuid)
    os.makedirs(work_dir, exist_ok=True)
    dest_path = os.path.join(work_dir, filename)
    
    # Move file to temporary UUID folder
    shutil.move(source_path, dest_path)

    # 2. Generate metadata.json
    exif_content = get_exif_data(dest_path)
    
    combined_metadata = {
        "metadata": {
            "original_filename": filename,
            "original_fullpath": source_path,
            "run_timestamp": run_timestamp,
            "main_folder": main_folder,
            "sub_folder": sub_folder,
            "file_uuid": file_uuid,
            "sha256": file_hash
        },
        "exif": exif_content
    }

    metadata_path = os.path.join(work_dir, "metadata.json")
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(combined_metadata, f, indent=4)

    # 3. Concurrent Duplicate Check
    is_duplicate = False
    with db_lock:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO photos (hash, uuid, original_path) VALUES (?, ?, ?)", 
                (file_hash, file_uuid, dest_path)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            is_duplicate = True
        finally:
            conn.close()

    # 4. Final Routing
    if is_duplicate:
        dup_dir = os.path.join(DUPLICATES_DIR, file_hash, file_uuid)
        os.makedirs(os.path.dirname(dup_dir), exist_ok=True)
        shutil.move(work_dir, dup_dir)
        print(f"[DUPLICATE] {filename} -> Moved to duplicates/{file_hash}")
    else:
        print(f"[OK] {filename} -> Moved to in_progress/{file_uuid}")

def main():
    # Ensure directories exist
    for d in [IMPORT_DIR, IN_PROGRESS_DIR, DUPLICATES_DIR]:
        os.makedirs(d, exist_ok=True)

    # Init SQLite
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS photos (hash TEXT PRIMARY KEY, uuid TEXT, original_path TEXT)")
    conn.close()

    # Scan for files: project/import/main/sub/image.ext
    tasks = []
    for main_f in os.listdir(IMPORT_DIR):
        main_p = os.path.join(IMPORT_DIR, main_f)
        if not os.path.isdir(main_p): continue
        
        for sub_f in os.listdir(main_p):
            sub_p = os.path.join(main_p, sub_f)
            if not os.path.isdir(sub_p): continue
            
            for img in os.listdir(sub_p):
                img_p = os.path.join(sub_p, img)
                if os.path.isfile(img_p):
                    tasks.append((main_f, sub_f, img, img_p))

    # Multithreading execution
    print(f"Starting process for {len(tasks)} files...")
    with ThreadPoolExecutor(max_workers=8) as executor:
        executor.map(process_file, tasks)

if __name__ == "__main__":
    main()