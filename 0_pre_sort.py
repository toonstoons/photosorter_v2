import os
import re
import shutil
import exiftool
import reverse_geocode as rg_fast  # This is the lightweight version
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCE_DIR = os.path.join(BASE_DIR, "presort")
DEST_DIR = os.path.join(BASE_DIR, "presorted")
ERROR_DIR = os.path.join(BASE_DIR, "error")
EXIFTOOL_PATH = os.path.join(BASE_DIR, "bin", "linux", "Image-ExifTool-13.58", "exiftool")

ALLOWED_EXTENSIONS = {'.JPG', '.JPEG', '.PNG', '.MP4', '.RAF','.CR2'}  # Added RAF for Fujifilm RAW files

def parse_exif_datetime(date_str):
    value = str(date_str).strip()
    if not value:
        return None

    # Normalize common EXIF/QuickTime datetime variants.
    value = value.replace("T", " ")
    value = re.sub(r"(\.\d+)(?=(Z|[+-]\d{2}:?\d{2})?$)", "", value)
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"

    # Handle malformed values such as 'YYYY:MM:DD HH:MM:' or missing seconds.
    if re.match(r"^\d{4}:\d{2}:\d{2} \d{2}:\d{2}:$", value):
        value += "00"
    elif re.match(r"^\d{4}:\d{2}:\d{2} \d{2}:\d{2}$", value):
        value += ":00"

    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y:%m:%d %H:%M:%S%z"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None

def get_unique_path(target_dir, filename):
    base, ext = os.path.splitext(filename)
    counter = 1
    unique_path = os.path.join(target_dir, filename)
    while os.path.exists(unique_path):
        unique_path = os.path.join(target_dir, f"{base}_{counter}{ext}")
        counter += 1
    return unique_path

def get_exif_info(file_path):
    try:
        with exiftool.ExifToolHelper(executable=EXIFTOOL_PATH) as et:
            metadata = et.get_metadata(file_path)[0]

        date_str = metadata.get("EXIF:DateTimeOriginal") or metadata.get("QuickTime:CreateDate")
        if not date_str:
            return 'NO_EXIF', None, None

        date_str = str(date_str).strip()
        if date_str.startswith("0000"):
            return 'INVALID_YEAR', None, None

        dt = parse_exif_datetime(date_str)
        if dt is None:
            print(f"[DATE ERROR] Could not parse EXIF date '{date_str}' in {file_path}")
            return 'INVALID_DATE', None, None

        lat = metadata.get("Composite:GPSLatitude")
        lon = metadata.get("Composite:GPSLongitude")

        lat_lon = None
        if lat is not None and lon is not None:
            lat_lon = (float(lat), float(lon))

        return 'VALID', dt, lat_lon

    except Exception as e:
        print(f"[EXIF ERROR] Could not read EXIF data from {file_path}")
        print(f"Exception: {e}")
        return 'NO_EXIF', None, None

def route_file(file_path, source_subfolder, counter):
    print(f"[{counter}] Routing file: {file_path}")
    filename = os.path.basename(file_path)
    ext = os.path.splitext(filename)[1].upper()
    
    if ext not in ALLOWED_EXTENSIONS:
        target_dir = os.path.join(ERROR_DIR, source_subfolder, "filetype", ext.replace('.', ''))
        os.makedirs(target_dir, exist_ok=True)
        shutil.move(file_path, get_unique_path(target_dir, filename))
        return

    status, dt, lat_lon = get_exif_info(file_path)
    
    if status in ('INVALID_YEAR', 'INVALID_DATE'):
        target_dir = os.path.join(ERROR_DIR, source_subfolder, "date_error")
        os.makedirs(target_dir, exist_ok=True)
        shutil.move(file_path, get_unique_path(target_dir, filename))
        return
    elif status == 'NO_EXIF':
        target_dir = os.path.join(ERROR_DIR, source_subfolder, "no_exif")
        os.makedirs(target_dir, exist_ok=True)
        shutil.move(file_path, get_unique_path(target_dir, filename))
        return

    year, month, day = dt.strftime("%Y"), dt.strftime("%m"), dt.strftime("%d")

    if lat_lon:
        # reverse-geocode search expects a list of tuples
        # returns a list of dicts: [{'country_code': 'US', 'city': 'New York City', 'country': 'United States'}]
        result = rg_fast.search([lat_lon])[0]
        country = result['country_code'].upper() 
        city = result['city'].upper().replace(" ", "_")
        final_dir = os.path.join(DEST_DIR, source_subfolder, country, city)
    else:
        final_dir = os.path.join(DEST_DIR, source_subfolder, "NO_COORDS", f"{year}_{month}_{day}")

    os.makedirs(final_dir, exist_ok=True)
    final_destination = get_unique_path(final_dir, filename)
    
    try:
        shutil.move(file_path, final_destination)
        print(f"[SORTED] [{counter}] {filename} -> {final_dir.replace(DEST_DIR, '')}")
    except Exception as e:
        print(f"[ERROR] {filename}: {e}")

def main():
    print("Starting Pre-Sort (Lightweight Geocoding)...")
    
    if not os.path.exists(SOURCE_DIR):
        print(f"Source directory {SOURCE_DIR} not found.")
        return

    files_to_process = []

    source_subfolders = [
        d for d in os.listdir(SOURCE_DIR)
        if os.path.isdir(os.path.join(SOURCE_DIR, d))
    ]

    for subfolder in source_subfolders:
        subfolder_path = os.path.join(SOURCE_DIR, subfolder)
        for root, _, files in os.walk(subfolder_path):
            for f in files:
                files_to_process.append((os.path.join(root, f), subfolder))

    if not files_to_process:
        print("No files to process...")
        return

    print(f"Processing {len(files_to_process)} files...")
    
    # Using 10 workers since this library has almost no overhead
    with ThreadPoolExecutor(max_workers=10) as executor:
        i=0
        for file_path, subfolder in files_to_process:
            i += 1
            print(f"Processing file {i}/{len(files_to_process)}: {file_path}")
            executor.submit(route_file, file_path, subfolder, i)

if __name__ == "__main__":
    main()