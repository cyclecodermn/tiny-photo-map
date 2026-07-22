#!/usr/bin/env python3
"""Refresh the Tiny Photo Map JSON photo catalog."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import struct
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
PHOTO_DIR = PUBLIC / "sample_photos"
CATALOG_PATH = PUBLIC / "photos.json"
OVERRIDES_PATH = PUBLIC / "photo_overrides.json"
TITLE_SOURCE_PATH = ROOT / "title.md"
TITLE_DATA_PATH = PUBLIC / "title.json"
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".svg"}
JPEG_EXTENSIONS = {".jpg", ".jpeg"}
SCHEMA_VERSION = 1
OREGON_TIME = ZoneInfo("America/Los_Angeles")
APPROVED_OVERRIDE_FIELDS = {
    "id",
    "caption",
    "date",
    "image",
    "alt",
    "demoLocation",
    "demoLocationNote",
    "lat",
    "lon",
}


@dataclass
class RefreshMessage:
    kind: str
    path: str
    detail: str


@dataclass
class RefreshResult:
    discovered: int = 0
    written: bool = False
    unchanged: bool = False
    missing_gps: list[str] = field(default_factory=list)
    missing_date: list[str] = field(default_factory=list)
    unreadable: list[RefreshMessage] = field(default_factory=list)
    unsupported: list[str] = field(default_factory=list)
    duplicates: list[RefreshMessage] = field(default_factory=list)
    override_errors: list[str] = field(default_factory=list)

    @property
    def blocking_problem_count(self) -> int:
        return len(self.unreadable) + len(self.duplicates) + len(self.override_errors)


def slugify(filename: str) -> str:
    stem = Path(filename).stem.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", stem).strip("-")
    return slug or "photo"


def unique_id(filename: str, used: dict[str, str]) -> str:
    base = slugify(filename)
    candidate = base
    index = 2
    while candidate in used and used[candidate] != filename:
        candidate = f"{base}-{index}"
        index += 1
    used[candidate] = filename
    return candidate


def json_bytes(data: dict[str, Any]) -> bytes:
    return (json.dumps(data, indent=2, sort_keys=True) + "\n").encode("utf-8")


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_overrides(path: Path) -> tuple[dict[str, dict[str, Any]], list[str]]:
    if not path.exists():
        return {}, []

    try:
        raw = read_json(path)
    except json.JSONDecodeError as exc:
        return {}, [f"{path}: malformed JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"]
    except OSError as exc:
        return {}, [f"{path}: could not read overrides: {exc}"]

    if not isinstance(raw, dict):
        return {}, [f"{path}: expected a JSON object"]

    photos = raw.get("photos", [])
    if not isinstance(photos, list):
        return {}, [f"{path}: expected photos to be a list"]

    overrides: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for index, item in enumerate(photos):
        if not isinstance(item, dict):
            errors.append(f"{path}: photos[{index}] must be an object")
            continue

        image = item.get("image")
        if not isinstance(image, str) or not image:
            errors.append(f"{path}: photos[{index}] needs a non-empty image string")
            continue

        clean = {key: value for key, value in item.items() if key in APPROVED_OVERRIDE_FIELDS}
        overrides[image] = clean

    return overrides, errors


def parse_title_markdown(content: str) -> tuple[dict[str, Any], list[str]]:
    title = ""
    subtitle = ""
    paragraphs: list[str] = []
    current_paragraph: list[str] = []
    errors: list[str] = []

    def finish_paragraph() -> None:
        if current_paragraph:
            paragraphs.append(" ".join(current_paragraph))
            current_paragraph.clear()

    for line_number, raw_line in enumerate(content.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            finish_paragraph()
            continue
        if line.startswith("# "):
            finish_paragraph()
            if title:
                errors.append(f"title.md:{line_number}: only one # album title is supported")
            title = line[2:].strip()
        elif line.startswith("## "):
            finish_paragraph()
            if subtitle:
                errors.append(f"title.md:{line_number}: only one ## subtitle is supported")
            subtitle = line[3:].strip()
        elif line.startswith("#"):
            errors.append(f"title.md:{line_number}: unsupported heading level")
        else:
            current_paragraph.append(line)

    finish_paragraph()
    if not title:
        errors.append("title.md: missing # album title")

    return {"schemaVersion": SCHEMA_VERSION, "title": title, "subtitle": subtitle, "paragraphs": paragraphs}, errors


def load_title(source_path: Path = TITLE_SOURCE_PATH) -> tuple[dict[str, Any], list[str]]:
    if not source_path.exists():
        return {"schemaVersion": SCHEMA_VERSION, "title": "", "subtitle": "", "paragraphs": []}, [
            f"{source_path}: missing title.md"
        ]
    try:
        return parse_title_markdown(source_path.read_text(encoding="utf-8"))
    except OSError as exc:
        return {"schemaVersion": SCHEMA_VERSION, "title": "", "subtitle": "", "paragraphs": []}, [
            f"{source_path}: could not read title.md: {exc}"
        ]


def rational_value(value: Any) -> float | None:
    if isinstance(value, tuple) and len(value) == 2:
        numerator, denominator = value
        if denominator:
            return float(numerator) / float(denominator)
    return None


def gps_coordinate(values: Any, ref: str | None) -> float | None:
    if not isinstance(values, list) or len(values) != 3:
        return None

    parts = [rational_value(value) for value in values]
    if any(part is None for part in parts):
        return None

    degrees, minutes, seconds = parts
    coordinate = degrees + minutes / 60 + seconds / 3600
    if ref in {"S", "W"}:
        coordinate *= -1
    return coordinate


class ExifReader:
    def __init__(self, data: bytes):
        self.data = data
        self.endian = ">"
        self.tiff_start = 0

    def read_jpeg_exif(self) -> dict[str, Any]:
        if not self.data.startswith(b"\xff\xd8"):
            raise ValueError("not a JPEG file")

        offset = 2
        while offset + 4 <= len(self.data):
            if self.data[offset] != 0xFF:
                raise ValueError("invalid JPEG segment")

            marker = self.data[offset + 1]
            offset += 2
            if marker in {0xD8, 0xD9}:
                continue
            if offset + 2 > len(self.data):
                break

            length = struct.unpack(">H", self.data[offset : offset + 2])[0]
            segment_start = offset + 2
            segment_end = offset + length
            if length < 2 or segment_end > len(self.data):
                raise ValueError("invalid JPEG segment length")

            segment = self.data[segment_start:segment_end]
            if marker == 0xE1 and segment.startswith(b"Exif\x00\x00"):
                return self.parse_tiff(segment[6:])

            offset = segment_end

        return {}

    def parse_tiff(self, tiff: bytes) -> dict[str, Any]:
        self.data = tiff
        self.tiff_start = 0
        if len(tiff) < 8:
            raise ValueError("short EXIF TIFF data")

        byte_order = tiff[:2]
        if byte_order == b"II":
            self.endian = "<"
        elif byte_order == b"MM":
            self.endian = ">"
        else:
            raise ValueError("invalid EXIF byte order")

        if self.unpack("H", 2) != 42:
            raise ValueError("invalid EXIF TIFF marker")

        first_ifd = self.unpack("I", 4)
        tags = self.parse_ifd(first_ifd)
        exif_tags = self.parse_ifd(tags.get(0x8769, 0)) if isinstance(tags.get(0x8769), int) else {}
        gps_tags = self.parse_ifd(tags.get(0x8825, 0)) if isinstance(tags.get(0x8825), int) else {}

        date_time = exif_tags.get(0x9003) or exif_tags.get(0x9004) or tags.get(0x0132)
        offset_time = exif_tags.get(0x9011) or exif_tags.get(0x9012) or exif_tags.get(0x9010)
        date = None
        if isinstance(date_time, str) and re.match(r"^\d{4}:\d{2}:\d{2}", date_time):
            date = date_time[:10].replace(":", "-")
        else:
            date_time = None
        if not (isinstance(offset_time, str) and re.match(r"^[+-]\d{2}:\d{2}$", offset_time)):
            offset_time = None

        lat = gps_coordinate(gps_tags.get(0x0002), gps_tags.get(0x0001))
        lon = gps_coordinate(gps_tags.get(0x0004), gps_tags.get(0x0003))
        return {"date": date, "dateTime": date_time, "offsetTime": offset_time, "lat": lat, "lon": lon}

    def unpack(self, fmt: str, offset: int) -> int:
        size = struct.calcsize(fmt)
        if offset < 0 or offset + size > len(self.data):
            raise ValueError("EXIF offset out of range")
        return struct.unpack(self.endian + fmt, self.data[offset : offset + size])[0]

    def parse_ifd(self, offset: int) -> dict[int, Any]:
        if offset <= 0:
            return {}
        if offset + 2 > len(self.data):
            raise ValueError("EXIF IFD offset out of range")

        count = self.unpack("H", offset)
        entries_start = offset + 2
        tags: dict[int, Any] = {}
        for index in range(count):
            entry = entries_start + index * 12
            if entry + 12 > len(self.data):
                raise ValueError("EXIF IFD entry out of range")

            tag = self.unpack("H", entry)
            field_type = self.unpack("H", entry + 2)
            field_count = self.unpack("I", entry + 4)
            value_offset = entry + 8
            tags[tag] = self.read_value(field_type, field_count, value_offset)

        return tags

    def read_value(self, field_type: int, count: int, value_offset: int) -> Any:
        type_sizes = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8}
        if field_type not in type_sizes:
            return None

        total_size = type_sizes[field_type] * count
        data_offset = value_offset if total_size <= 4 else self.unpack("I", value_offset)
        if data_offset < 0 or data_offset + total_size > len(self.data):
            raise ValueError("EXIF value offset out of range")

        raw = self.data[data_offset : data_offset + total_size]
        if field_type == 2:
            return raw.split(b"\x00", 1)[0].decode("utf-8", errors="replace")
        if field_type == 3:
            values = [struct.unpack(self.endian + "H", raw[i : i + 2])[0] for i in range(0, total_size, 2)]
            return values[0] if count == 1 else values
        if field_type == 4:
            values = [struct.unpack(self.endian + "I", raw[i : i + 4])[0] for i in range(0, total_size, 4)]
            return values[0] if count == 1 else values
        if field_type == 5:
            values = []
            for i in range(0, total_size, 8):
                values.append(struct.unpack(self.endian + "II", raw[i : i + 8]))
            return values[0] if count == 1 else values
        if field_type == 1:
            return raw[0] if count == 1 else list(raw)
        return None


def read_exif(path: Path) -> tuple[dict[str, Any], str | None]:
    try:
        data = path.read_bytes()
        return ExifReader(data).read_jpeg_exif(), None
    except (OSError, ValueError, struct.error) as exc:
        return {}, str(exc)


def default_caption(filename: str) -> str:
    stem = Path(filename).stem
    friendly = friendly_numeric_caption(stem)
    if friendly:
        return friendly
    words = re.sub(r"[_-]+", " ", stem).strip()
    return words.title() if words else filename


def parse_camera_filename_datetime(stem: str) -> datetime | None:
    match = re.fullmatch(r"(\d{8})[ _](\d{6})(?:\(\d+\))?", stem)
    if not match:
        return None
    try:
        return datetime.strptime("".join(match.groups()), "%Y%m%d%H%M%S")
    except ValueError:
        return None


def friendly_datetime(value: datetime) -> str:
    hour = value.strftime("%I").lstrip("0")
    return f"{value.day} {value.strftime('%b')} {value.year}, {hour}:{value.strftime('%M')} {value.strftime('%p')}"


def friendly_numeric_caption(stem: str, exif: dict[str, Any] | None = None) -> str | None:
    camera_time = parse_camera_filename_datetime(stem)
    if camera_time is None:
        return None

    exif = exif or {}
    date_time = exif.get("dateTime")
    offset_time = exif.get("offsetTime")
    if isinstance(date_time, str) and isinstance(offset_time, str):
        try:
            aware = datetime.strptime(date_time + offset_time, "%Y:%m:%d %H:%M:%S%z")
            return friendly_datetime(aware)
        except ValueError:
            pass

    return friendly_datetime(camera_time.replace(tzinfo=OREGON_TIME))


def discover_photo_files(photo_dir: Path) -> tuple[list[Path], list[str]]:
    files: list[Path] = []
    unsupported: list[str] = []
    for path in sorted(photo_dir.iterdir(), key=lambda item: item.name.lower()):
        if not path.is_file():
            continue
        if path.suffix.lower() in SUPPORTED_EXTENSIONS:
            files.append(path)
        else:
            unsupported.append(path.name)
    return files, unsupported


def build_catalog(public_dir: Path = PUBLIC) -> tuple[dict[str, Any], RefreshResult]:
    photo_dir = public_dir / "sample_photos"
    overrides_path = public_dir / "photo_overrides.json"
    result = RefreshResult()
    overrides, override_errors = load_overrides(overrides_path)
    result.override_errors.extend(override_errors)

    files, unsupported = discover_photo_files(photo_dir)
    result.unsupported.extend(unsupported)

    by_canonical_name: dict[str, Path] = {}
    used_ids: dict[str, str] = {}
    records: list[dict[str, Any]] = []

    for path in files:
        result.discovered += 1
        canonical = path.name.lower()
        if canonical in by_canonical_name:
            result.duplicates.append(
                RefreshMessage(
                    "duplicate",
                    path.name,
                    f"collides with {by_canonical_name[canonical].name} after case normalization",
                )
            )
            continue
        by_canonical_name[canonical] = path

        relative_image = f"sample_photos/{path.name}"
        exif: dict[str, Any] = {}
        record: dict[str, Any] = {
            "id": unique_id(path.name, used_ids),
            "caption": default_caption(path.name),
            "date": None,
            "image": relative_image,
            "alt": default_caption(path.name),
        }

        if path.suffix.lower() in JPEG_EXTENSIONS:
            exif, error = read_exif(path)
            if error:
                result.unreadable.append(RefreshMessage("unreadable", path.name, error))
            record.update({key: exif[key] for key in ("date", "lat", "lon") if exif.get(key) is not None})

        friendly_caption = friendly_numeric_caption(path.stem, exif)
        if friendly_caption:
            record["caption"] = friendly_caption
            record["alt"] = friendly_caption

        override = overrides.get(relative_image, {})
        record.update(override)
        if not record.get("date"):
            result.missing_date.append(path.name)
        if not (isinstance(record.get("lat"), int | float) and isinstance(record.get("lon"), int | float)):
            result.missing_gps.append(path.name)

        records.append(record)

    records.sort(key=lambda item: (item.get("date") or "9999-99-99", item.get("image") or ""))
    return {"schemaVersion": SCHEMA_VERSION, "photos": records}, result


def atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
        os.chmod(temp_path, mode)
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def print_summary(result: RefreshResult, catalog_path: Path) -> None:
    print(
        "Summary: "
        f"discovered={result.discovered}, "
        f"written={int(result.written)}, "
        f"unchanged={int(result.unchanged)}, "
        f"missing_gps={len(result.missing_gps)}, "
        f"missing_date={len(result.missing_date)}, "
        f"unreadable={len(result.unreadable)}, "
        f"unsupported={len(result.unsupported)}, "
        f"duplicates/collisions={len(result.duplicates)}"
    )
    print(f"Catalog: {catalog_path}")

    details = [
        ("Missing GPS", result.missing_gps),
        ("Missing date", result.missing_date),
        ("Unsupported files", result.unsupported),
    ]
    for label, items in details:
        if items:
            print(f"{label}: {', '.join(items)}")
    for message in result.unreadable:
        print(f"Unreadable: {message.path}: {message.detail}")
    for message in result.duplicates:
        print(f"Duplicate/collision: {message.path}: {message.detail}")
    for error in result.override_errors:
        print(f"Override error: {error}")


def refresh(public_dir: Path, check: bool = False) -> int:
    catalog_path = public_dir / "photos.json"
    title_path = public_dir / "title.json"
    catalog, result = build_catalog(public_dir)
    title, title_errors = load_title(ROOT / "title.md")
    result.override_errors.extend(title_errors)
    content = json_bytes(catalog)
    title_content = json_bytes(title)
    existing = catalog_path.read_bytes() if catalog_path.exists() else None
    existing_title = title_path.read_bytes() if title_path.exists() else None

    if result.blocking_problem_count:
        print_summary(result, catalog_path)
        print("Refresh failed: blocking catalog input problems were found.")
        return 1

    if existing == content and existing_title == title_content:
        result.unchanged = True
    elif check:
        result.unchanged = False
    else:
        atomic_write(catalog_path, content)
        atomic_write(title_path, title_content)
        result.written = True

    print_summary(result, catalog_path)
    if check and (existing != content or existing_title != title_content):
        print("Check failed: generated public data would change.")
        return 1
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        "--dry-run",
        action="store_true",
        dest="check",
        help="report proposed changes without replacing photos.json",
    )
    parser.add_argument(
        "--public-dir",
        type=Path,
        default=PUBLIC,
        help=argparse.SUPPRESS,
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        return refresh(args.public_dir, check=args.check)
    except FileNotFoundError as exc:
        print(f"Refresh failed: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Refresh failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
