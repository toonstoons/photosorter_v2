import os
import json
import shutil
import re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# --- CONFIGURATION ---
BASE_DIR = os.getcwd()
IN_PROGRESS_DIR = os.path.join(BASE_DIR, "in_progress")
SORTED_DIR = os.path.join(BASE_DIR, "sorted")

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

    # 1. Date Extraction
    date_str = exif.get("EXIF DateTimeOriginal")
    try:
        dt = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
    except (ValueError, TypeError):
        dt = datetime.now()

    # 2. Extract and Format Make/Model (Combined max 10 chars)
    raw_make = exif.get("Image Make", "")
    raw_model = exif.get("Image Model", "")
    # Combine first, then sanitize and truncate to 10
    make_model_combined = sanitize_and_format(f"{raw_make}{raw_model}", max_len=10)
    if not make_model_combined:
        make_model_combined = "UNKNOWN"

    # 3. Path Variables (Capitalized)
    year = dt.strftime("%Y")
    month_day = dt.strftime("%m_%d")
    hms = dt.strftime("%H%M%S")
    
    main_folder = sanitize_and_format(meta.get("main_folder", "UNKNOWNMAIN"))
    sub_folder = sanitize_and_format(meta.get("sub_folder", "UNKNOWNSUB"))
    ext = os.path.splitext(meta.get("original_filename", ""))[1].upper()

    # 4. Final Path Construction
    # Directory: YEAR_MAIN_FOLDER (e.g., 2024_VACATION)
    target_dir_name = f"{year}_{main_folder}"
    target_dir_path = os.path.join(SORTED_DIR, target_dir_name)
    os.makedirs(target_dir_path, exist_ok=True)

    # Filename: MONTH_DAY_HOURMINUTESECONDS_SUBFOLDER_MAKEMODEL.EXT
    # Everything is already forced to upper in steps above, but we'll ensure it here
    name_part = f"{month_day}_{hms}_{sub_folder}_{make_model_combined}"
    final_filename = f"{name_part}{ext}".upper()
    
    final_destination = os.path.join(target_dir_path, final_filename)

    # 5. Move and Cleanup
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
        except Exception as e:
            print(f"[ERROR] {e}")

def main():
    if not os.path.exists(IN_PROGRESS_DIR):
        return

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

    with ThreadPoolExecutor(max_workers=8) as executor:
        executor.map(process_sorted_move, all_uuid_dirs)

if __name__ == "__main__":
    main()