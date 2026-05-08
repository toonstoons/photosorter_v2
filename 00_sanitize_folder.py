import argparse
import os
import shutil
from pathlib import Path


ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".mp4",".raf"}
IGNORED_ROOT_FOLDERS = {"supported", "unsupported"}


def unique_destination_path(destination_dir: Path, filename: str, folder_name: str) -> Path:
	stem, suffix = os.path.splitext(filename)

	if suffix.lower() not in ALLOWED_EXTENSIONS:
		target = destination_dir / f"unsupported_{folder_name}" /suffix.replace('.', '')
		target.mkdir(parents=True, exist_ok=True)
		target = target / filename
	else:
		target = destination_dir /f"supported_{folder_name}"
		target.mkdir(parents=True, exist_ok=True)
		target = target / filename
	if not target.exists():
		return target

	counter = 1
	while True:

		if suffix.lower() not in ALLOWED_EXTENSIONS:
			candidate = destination_dir / f"unsupported_{folder_name}" /f"{stem}_{counter}{suffix}"

		else:
			candidate = destination_dir / f"supported_{folder_name}" /f"{stem}_{counter}{suffix}"

		if not candidate.exists():
			return candidate
		counter += 1

def move_files_to_root(root_dir: Path, max_depth: int) -> int:
	moved_count = 0
	root_dir = root_dir.resolve()

	for current_root, dirs, files in os.walk(root_dir):
		current_path = Path(current_root)

		if current_path == root_dir:
			dirs[:] = [
				d for d in dirs
				if d not in IGNORED_ROOT_FOLDERS and not d.startswith("supported_") and not d.startswith("unsupported_")
			]

		relative_parts = current_path.relative_to(root_dir).parts
		depth = len(relative_parts)

		if depth > max_depth:
			continue

		for filename in files:
			source = current_path / filename
			# if source.suffix.lower() not in ALLOWED_EXTENSIONS:
			# 	continue
			folder_name= root_dir.parent.name
			destination = unique_destination_path(root_dir, source.name,folder_name)
			if source.resolve() == destination.resolve():
				print(f"[SKIPPED] source and destination are the same: {source}")
				continue
			shutil.move(str(source), str(destination))
			moved_count += 1
			print(f"[MOVED] {source} -> {destination}")

	return moved_count


def delete_empty_subfolders(root_dir: Path) -> int:
	removed_count = 0
	root_dir = root_dir.resolve()

	for current_root, _, _ in os.walk(root_dir, topdown=False):
		current_path = Path(current_root)
		if current_path == root_dir:
			continue

		# Remove only folders that became fully empty.
		if not any(current_path.iterdir()):
			current_path.rmdir()
			removed_count += 1
			print(f"[REMOVED EMPTY] {current_path}")

	return removed_count


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description=(
			"Move .jpg/.jpeg/.png/.mp4 files from subfolders up to a given depth "
			"into the provided root folder."
		)
	)
	parser.add_argument("path", help="Root folder path")
	parser.add_argument("level", type=int, help="Maximum depth to scan (must be >= 1)")
	return parser.parse_args()


def main() -> None:
	args = parse_args()
	root = Path(args.path).expanduser()

	if not root.exists() or not root.is_dir():
		raise SystemExit(f"Error: '{root}' is not a valid directory.")

	if args.level < 1:
		raise SystemExit("Error: level must be >= 1.")

	moved = move_files_to_root(root, args.level)
	removed = delete_empty_subfolders(root)
	print(f"Done. Moved {moved} file(s), removed {removed} empty folder(s).")


if __name__ == "__main__":
	main()
