import csv
import os
import json
import shutil
import re
import sqlite3
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IN_PROGRESS_DIR = os.path.join(BASE_DIR, "in_progress")
SORTED_DIR = os.path.join(BASE_DIR, "sorted")
DB_PATH = os.path.join(BASE_DIR, "duplicate_check.sqlite")
LOG_FIELDNAMES = ["timestamp", "country", "city", "file"]

_log_lock = threading.Lock()


def get_log_file_path(year: str) -> str:
    return os.path.join(BASE_DIR, f"{year}_sort_log.csv")


def append_log_entry(year: str, timestamp: str, country: str, city: str, filename: str) -> None:
    log_file = get_log_file_path(year)
    with _log_lock:
        file_exists = os.path.isfile(log_file)
        with open(log_file, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=LOG_FIELDNAMES)
            if not file_exists:
                writer.writeheader()
            writer.writerow({
                "timestamp": timestamp,
                "country": country,
                "city": city,
                "file": filename,
            })


def sanitize_and_format(text, max_len=None):
    """Removes non-alphanumeric, capitalizes, and optionally truncates."""
    if not text:
        return ""
    # Remove non-alphanumeric characters
    clean_text = re.sub(r'[^a-zA-Z0-9]', '', text)
    # Capitalize
    clean_text = clean_text.upper()
    # Truncate if necessary
    if max_len:
        clean_text = clean_text[:max_len]
    return clean_text

def process_sorted_move(task_dir):
    metadata_path = os.path.join(task_dir, "metadata.json")
    if not os.path.exists(metadata_path):
        return

    with open(metadata_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    meta = data.get("metadata", {})
    exif = data.get("exif", {})

    # Date Extraction
    date_str = exif.get("EXIF:DateTimeOriginal")
    try:
        dt = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
    except (ValueError, TypeError):
        dt = None
    # Extension Extraction
    try:
        original_filename = meta.get("original_filename", "")
        ext = os.path.splitext(original_filename)[1].upper()
    except Exception:
        ext = ".UNKNOWN"

    # Extract and Format Make/Model (Combined max 10 chars)
    raw_make = exif.get("EXIF:Make", "")
    raw_model = exif.get("EXIF:Model", "")
    # Combine first, then sanitize and truncate to 10
    make_model_combined = sanitize_and_format(f"{raw_make}{raw_model}", max_len=10)
    if not make_model_combined:
        make_model_combined = "UNKNOWN"

    # Path Variables (Capitalized)
    if dt is None:
        year = "0000"
        month_day = "00_00"
        hms = "000000"
        timestamp_value = "00000000"
    else:
        year = dt.strftime("%Y")
        month_day = dt.strftime("%m_%d")
        hms = dt.strftime("%H%M%S")
        timestamp_value = dt.strftime("%Y-%m-%dT%H:%M:%S")
    
    main_folder = sanitize_and_format(meta.get("main_folder", "UNKNOWNMAIN"))
    sub_folder = sanitize_and_format(meta.get("sub_folder", "UNKNOWNSUB"))
    try:
        ext = os.path.splitext(meta.get("original_filename", ""))[1].upper()
    except Exception:
        ext = ".UNKNOWN"

    if ext in [".RAW",".RAF",".CR2",".CR3",".NEF",".ARW"]:
        ext_folder = "RAW"
    elif ext in [".JPG", ".JPEG"]:
        ext_folder = "JPG"
    elif ext == ".UNKNOWN":
        ext_folder = "UNKNOWN"
    else:
        ext_folder = ext.replace('.', '')  # Remove dot for folder name
        ext_folder = sanitize_and_format(ext_folder)
    # Final Path Construction
    # Directory: YEAR_MAIN_FOLDER (e.g., 2024_VACATION)
    target_dir_name = f"{year}_{main_folder}"
    target_subfolder = f"{month_day}_{year}_{main_folder}_{sub_folder if sub_folder else "NO_SUBFOLDER"}"
    target_dir_path = os.path.join(SORTED_DIR, ext_folder, target_dir_name, target_subfolder)
    os.makedirs(target_dir_path, exist_ok=True)

    # Filename: MONTH_DAY_HOURMINUTESECONDS_SUBFOLDER_MAKEMODEL.EXT
    # Everything is already forced to upper in steps above, but we'll ensure it here
    name_part = f"{month_day}_{hms}_{sub_folder}_{make_model_combined}"
    final_filename = f"{name_part}{ext}".upper()
    
    final_destination = os.path.join(target_dir_path, final_filename)

    # Move and Cleanup
    photo_file = None
    for f in os.listdir(task_dir):
        if f != "metadata.json":
            photo_file = os.path.join(task_dir, f)
            break
    
    if photo_file:
        try:
            shutil.move(photo_file, final_destination)
            shutil.rmtree(task_dir)
            print(f"[SORTED] {final_filename}")
            file_hash = meta.get("sha256")
            if file_hash and os.path.exists(DB_PATH):
                conn = sqlite3.connect(DB_PATH)
                try:
                    conn.execute(
                        "UPDATE photos SET current_path = ? WHERE hash = ?",
                        (final_destination, file_hash),
                    )
                    conn.commit()
                finally:
                    conn.close()
            append_log_entry(
                year=year,
                timestamp=timestamp_value,
                country=main_folder,
                city=sub_folder,
                filename=final_filename,
            )
        except Exception as e:
            print(f"[ERROR] {e}")

def main():
    if not os.path.exists(IN_PROGRESS_DIR):
        print(f"In-progress directory {IN_PROGRESS_DIR} not found.")
        return
    print(f"{IN_PROGRESS_DIR} Starting Final Sort and Move... " )
    all_uuid_dirs = []
    for main_f in os.listdir(IN_PROGRESS_DIR):
        main_p = os.path.join(IN_PROGRESS_DIR, main_f)
        if os.path.isdir(main_p):
            for sub_f in os.listdir(main_p):
                sub_p = os.path.join(main_p, sub_f)
                if os.path.isdir(sub_p):
                    for uuid_f in os.listdir(sub_p):
                        uuid_p = os.path.join(sub_p, uuid_f)
                        if os.path.isdir(uuid_p):
                            all_uuid_dirs.append(uuid_p)
    print(f"Found {len(all_uuid_dirs)} files to process.")
    with ThreadPoolExecutor(max_workers=8) as executor:
        executor.map(process_sorted_move, all_uuid_dirs)

if __name__ == "__main__":
    main()