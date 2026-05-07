import os
import shutil
import exifread
import reverse_geocode as rg_fast  # This is the lightweight version
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# --- CONFIGURATION ---
BASE_DIR = os.getcwd()
SOURCE_DIR = os.path.join(BASE_DIR, "presort")
DEST_DIR = os.path.join(BASE_DIR, "presorted")
ERROR_DIR = os.path.join(BASE_DIR, "error")

ALLOWED_EXTENSIONS = {'.JPG', '.JPEG', '.PNG', '.MP4'}

def get_unique_path(target_dir, filename):
    base, ext = os.path.splitext(filename)
    counter = 1
    unique_path = os.path.join(target_dir, filename)
    while os.path.exists(unique_path):
        unique_path = os.path.join(target_dir, f"{base}_{counter}{ext}")
        counter += 1
    return unique_path

def convert_to_degrees(value):
    d = float(value.values[0].num) / float(value.values[0].den)
    m = float(value.values[1].num) / float(value.values[1].den)
    s = float(value.values[2].num) / float(value.values[2].den)
    return d + (m / 60.0) + (s / 3600.0)

def get_exif_info(file_path):
    try:
        with open(file_path, 'rb') as f:
            tags = exifread.process_file(f, details=False)
            
            date_tag = tags.get("EXIF DateTimeOriginal")
            if not date_tag:
                return 'NO_EXIF', None, None
            
            date_str = str(date_tag).strip()
            if date_str.startswith("0000"):
                return 'INVALID_YEAR', None, None
            
            dt = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")

            lat_tag = tags.get("GPS GPSLatitude")
            lat_ref = tags.get("GPS GPSLatitudeRef")
            lon_tag = tags.get("GPS GPSLongitude")
            lon_ref = tags.get("GPS GPSLongitudeRef")

            lat_lon = None
            if lat_tag and lat_ref and lon_tag and lon_ref:
                lat = convert_to_degrees(lat_tag)
                if lat_ref.values[0] != 'N': lat = -lat
                lon = convert_to_degrees(lon_tag)
                if lon_ref.values[0] != 'E': lon = -lon
                lat_lon = (lat, lon)

            return 'VALID', dt, lat_lon
            
    except Exception:
        return 'NO_EXIF', None, None

def route_file(file_path):
    filename = os.path.basename(file_path)
    ext = os.path.splitext(filename)[1].upper()
    
    if ext not in ALLOWED_EXTENSIONS:
        target_dir = os.path.join(ERROR_DIR, "filetype", ext.replace('.', ''))
        os.makedirs(target_dir, exist_ok=True)
        shutil.move(file_path, get_unique_path(target_dir, filename))
        return

    status, dt, lat_lon = get_exif_info(file_path)
    
    if status == 'INVALID_YEAR':
        target_dir = os.path.join(ERROR_DIR, "date_error")
        os.makedirs(target_dir, exist_ok=True)
        shutil.move(file_path, get_unique_path(target_dir, filename))
        return
    elif status == 'NO_EXIF':
        target_dir = os.path.join(ERROR_DIR, "no_exif")
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
        final_dir = os.path.join(DEST_DIR, country, city, year, month, day)
    else:
        final_dir = os.path.join(DEST_DIR, "NO_COORDS", year, month, day)

    os.makedirs(final_dir, exist_ok=True)
    final_destination = get_unique_path(final_dir, filename)
    
    try:
        shutil.move(file_path, final_destination)
        print(f"[SORTED] {filename} -> {final_dir.replace(DEST_DIR, '')}")
    except Exception as e:
        print(f"[ERROR] {filename}: {e}")

def main():
    print("Starting Pre-Sort (Lightweight Geocoding)...")
    
    if not os.path.exists(SOURCE_DIR):
        print(f"Source directory {SOURCE_DIR} not found.")
        return

    files_to_process = [os.path.join(SOURCE_DIR, f) for f in os.listdir(SOURCE_DIR) 
                        if os.path.isfile(os.path.join(SOURCE_DIR, f))]

    if not files_to_process:
        print("No files to process...")
        return

    print(f"Processing {len(files_to_process)} files...")
    
    # Using 10 workers since this library has almost no overhead
    with ThreadPoolExecutor(max_workers=10) as executor:
        executor.map(route_file, files_to_process)

if __name__ == "__main__":
    main()