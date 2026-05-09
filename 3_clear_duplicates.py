import os
import shutil


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DUPLICATES_DIR = os.path.join(BASE_DIR, "duplicates")


def resolve_project_path(path_value):
	if os.path.isabs(path_value):
		return path_value
	return os.path.normpath(os.path.join(BASE_DIR, path_value))


def read_original_path(uuid_dir):
	original_path_file = os.path.join(uuid_dir, "original.txt")
	if not os.path.isfile(original_path_file):
		return None

	with open(original_path_file, "r", encoding="utf-8") as f:
		original_path = f.read().strip()

	return original_path or None


def cleanup_hash_dir(hash_dir):
	if os.path.isdir(hash_dir) and not os.listdir(hash_dir):
		os.rmdir(hash_dir)


def process_duplicate_uuid(uuid_dir):
	original_path = read_original_path(uuid_dir)
	if not original_path:
		print(f"[SKIP] Missing original.txt or empty path: {uuid_dir}")
		return False

	resolved_original_path = resolve_project_path(original_path)

	if not os.path.exists(resolved_original_path):
		print(f"[KEEP] Original file missing: {resolved_original_path}")
		return False

	shutil.rmtree(uuid_dir)
	print(f"[DELETED] {uuid_dir} -> original exists: {resolved_original_path}")
	return True


def main():
	if not os.path.isdir(DUPLICATES_DIR):
		print(f"Duplicates directory {DUPLICATES_DIR} not found.")
		return

	deleted_count = 0

	for hash_name in os.listdir(DUPLICATES_DIR):
		hash_dir = os.path.join(DUPLICATES_DIR, hash_name)
		if not os.path.isdir(hash_dir):
			continue

		uuid_dirs = [
			os.path.join(hash_dir, entry)
			for entry in os.listdir(hash_dir)
			if os.path.isdir(os.path.join(hash_dir, entry))
		]

		for uuid_dir in uuid_dirs:
			if process_duplicate_uuid(uuid_dir):
				deleted_count += 1

		cleanup_hash_dir(hash_dir)

	print(f"Finished. Deleted {deleted_count} duplicate folder(s).")


if __name__ == "__main__":
	main()
