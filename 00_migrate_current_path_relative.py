import argparse
import os
import sqlite3


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "duplicate_check.sqlite")


def classify_current_path(path_value: str):
    if not path_value:
        return path_value, "empty"

    normalized = os.path.normpath(path_value)
    if not os.path.isabs(normalized):
        return normalized, "already_relative"

    try:
        common = os.path.commonpath([BASE_DIR, normalized])
    except ValueError:
        return path_value, "outside_root"

    if common != BASE_DIR:
        return path_value, "outside_root"

    relative = os.path.normpath(os.path.relpath(normalized, BASE_DIR))
    return relative, "converted"


def migrate_current_paths(db_path: str, dry_run: bool = False):
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found: {db_path}")

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        rows = cursor.execute("SELECT hash, current_path FROM photos").fetchall()

        updates = []
        converted_count = 0
        already_relative_count = 0
        empty_count = 0
        outside_root_count = 0

        for file_hash, current_path in rows:
            new_path, status = classify_current_path(current_path)

            if status == "converted":
                converted_count += 1
                updates.append((new_path, file_hash))
            elif status == "already_relative":
                already_relative_count += 1
                if new_path != current_path:
                    updates.append((new_path, file_hash))
            elif status == "empty":
                empty_count += 1
            elif status == "outside_root":
                outside_root_count += 1

        if updates and not dry_run:
            cursor.executemany(
                "UPDATE photos SET current_path = ? WHERE hash = ?",
                updates,
            )
            conn.commit()

        return {
            "total_rows": len(rows),
            "updates": len(updates),
            "converted": converted_count,
            "already_relative": already_relative_count,
            "empty": empty_count,
            "outside_root": outside_root_count,
            "dry_run": dry_run,
        }
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate photos.current_path from absolute to project-relative paths."
    )
    parser.add_argument(
        "--db",
        default=DB_PATH,
        help="Path to duplicate_check.sqlite (defaults to project DB).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview migration counts without writing changes.",
    )
    args = parser.parse_args()

    try:
        stats = migrate_current_paths(args.db, dry_run=args.dry_run)
    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}")
        return
    except sqlite3.Error as exc:
        print(f"[ERROR] SQLite error: {exc}")
        return

    mode = "DRY RUN" if stats["dry_run"] else "MIGRATED"
    print(
        f"[{mode}] rows={stats['total_rows']} updates={stats['updates']} converted={stats['converted']} "
        f"already_relative={stats['already_relative']} empty={stats['empty']} outside_root={stats['outside_root']}"
    )


if __name__ == "__main__":
    main()
