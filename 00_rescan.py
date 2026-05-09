import os
import sqlite3


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "duplicate_check.sqlite")


def remove_missing_files(db_path: str) -> int:
	if not os.path.exists(db_path):
		raise FileNotFoundError(f"Database not found: {db_path}")

	conn = sqlite3.connect(db_path)
	deleted_count = 0

	try:
		cursor = conn.cursor()
		rows = cursor.execute("SELECT hash, current_path FROM photos").fetchall()

		missing_hashes = [
			file_hash
			for file_hash, current_path in rows
			if not current_path or not os.path.exists(current_path)
		]

		if missing_hashes:
			cursor.executemany(
				"DELETE FROM photos WHERE hash = ?",
				[(file_hash,) for file_hash in missing_hashes],
			)
			conn.commit()
			deleted_count = len(missing_hashes)
	finally:
		conn.close()

	return deleted_count


def main() -> None:
	try:
		deleted_count = remove_missing_files(DB_PATH)
	except FileNotFoundError as exc:
		print(f"[ERROR] {exc}")
		return
	except sqlite3.Error as exc:
		print(f"[ERROR] SQLite error: {exc}")
		return

	print(f"[DONE] Removed {deleted_count} stale entr{'y' if deleted_count == 1 else 'ies'} from photos")


if __name__ == "__main__":
	main()
