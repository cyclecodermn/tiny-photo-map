import contextlib
import io
import json
import os
import struct
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import refresh_photos


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def ifd_entry(tag, field_type, count, value):
    return struct.pack(">HHI4s", tag, field_type, count, value)


def ascii_value(value: str) -> tuple[int, bytes]:
    raw = value.encode("ascii") + b"\x00"
    return len(raw), raw


def rational(num: int, den: int) -> bytes:
    return struct.pack(">II", num, den)


def sample_jpeg_with_exif(date_time: str = "2024:07:04 12:34:56", offset_time: str | None = None) -> bytes:
    date_count, date_value = ascii_value(date_time)
    offset_count, offset_value = ascii_value(offset_time) if offset_time else (0, b"")
    tiff = bytearray(b"MM\x00*\x00\x00\x00\x08")

    ifd0_offset = 8
    ifd0_entries = 3
    exif_entries = 2 if offset_time else 1
    exif_ifd_offset = ifd0_offset + 2 + ifd0_entries * 12 + 4
    exif_value_offset = exif_ifd_offset + 2 + exif_entries * 12 + 4
    offset_value_offset = exif_value_offset + len(date_value)
    gps_ifd_offset = offset_value_offset + len(offset_value)
    gps_values_offset = gps_ifd_offset + 2 + 4 * 12 + 4

    tiff.extend(struct.pack(">H", ifd0_entries))
    tiff.extend(ifd_entry(0x8769, 4, 1, struct.pack(">I", exif_ifd_offset)))
    tiff.extend(ifd_entry(0x8825, 4, 1, struct.pack(">I", gps_ifd_offset)))
    tiff.extend(ifd_entry(0x0132, 2, date_count, struct.pack(">I", exif_value_offset)))
    tiff.extend(struct.pack(">I", 0))

    tiff.extend(struct.pack(">H", exif_entries))
    tiff.extend(ifd_entry(0x9003, 2, date_count, struct.pack(">I", exif_value_offset)))
    if offset_time:
        tiff.extend(ifd_entry(0x9011, 2, offset_count, struct.pack(">I", offset_value_offset)))
    tiff.extend(struct.pack(">I", 0))
    tiff.extend(date_value)
    tiff.extend(offset_value)

    lat_offset = gps_values_offset
    lon_offset = lat_offset + 24
    tiff.extend(struct.pack(">H", 4))
    tiff.extend(ifd_entry(0x0001, 2, 2, b"N\x00\x00\x00"))
    tiff.extend(ifd_entry(0x0002, 5, 3, struct.pack(">I", lat_offset)))
    tiff.extend(ifd_entry(0x0003, 2, 2, b"W\x00\x00\x00"))
    tiff.extend(ifd_entry(0x0004, 5, 3, struct.pack(">I", lon_offset)))
    tiff.extend(struct.pack(">I", 0))
    tiff.extend(rational(45, 1) + rational(30, 1) + rational(0, 1))
    tiff.extend(rational(122, 1) + rational(40, 1) + rational(30, 1))

    app1 = b"Exif\x00\x00" + bytes(tiff)
    return b"\xff\xd8" + b"\xff\xe1" + struct.pack(">H", len(app1) + 2) + app1 + b"\xff\xd9"


class RefreshPhotosTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.public = Path(self.tmp.name) / "public"
        (self.public / "sample_photos").mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def read_catalog(self):
        return json.loads((self.public / "photos.json").read_text(encoding="utf-8"))

    def test_extension_handling_and_stable_collision_ids(self):
        write_bytes(self.public / "sample_photos" / "Trip One.JPG", b"not-a-real-jpeg")
        write_bytes(self.public / "sample_photos" / "trip-one.jpeg", b"not-a-real-jpeg")

        catalog, result = refresh_photos.build_catalog(self.public)

        self.assertEqual([item["id"] for item in catalog["photos"]], ["trip-one", "trip-one-2"])
        self.assertEqual(result.discovered, 2)
        self.assertEqual(len(result.unreadable), 2)

    def test_case_duplicate_filenames_are_reported_and_not_duplicated(self):
        write_bytes(self.public / "sample_photos" / "Same.JPG", b"not-a-real-jpeg")
        write_bytes(self.public / "sample_photos" / "same.jpg", b"not-a-real-jpeg")

        catalog, result = refresh_photos.build_catalog(self.public)

        self.assertEqual(len(catalog["photos"]), 1)
        self.assertEqual(len(result.duplicates), 1)

    def test_exif_date_and_gps_are_read_from_jpeg(self):
        write_bytes(self.public / "sample_photos" / "mapped.jpg", sample_jpeg_with_exif())

        catalog, result = refresh_photos.build_catalog(self.public)
        photo = catalog["photos"][0]

        self.assertEqual(photo["date"], "2024-07-04")
        self.assertAlmostEqual(photo["lat"], 45.5)
        self.assertAlmostEqual(photo["lon"], -122.675)
        self.assertEqual(result.missing_date, [])
        self.assertEqual(result.missing_gps, [])

    def test_overrides_preserve_manual_fields_and_svg_demo_records(self):
        write_bytes(self.public / "sample_photos" / "demo.svg", b"<svg></svg>")
        write_text(
            self.public / "photo_overrides.json",
            json.dumps(
                {
                    "schemaVersion": 1,
                    "photos": [
                        {
                            "image": "sample_photos/demo.svg",
                            "id": "manual-id",
                            "caption": "Manual caption",
                            "date": "2026-01-02",
                            "alt": "Manual alt",
                            "demoLocation": "Manual location",
                            "demoLocationNote": "Manual note",
                            "lat": 45.0,
                            "lon": -122.0,
                            "ignoredExecutable": "alert(1)",
                        }
                    ],
                }
            ),
        )

        catalog, result = refresh_photos.build_catalog(self.public)

        self.assertEqual(result.blocking_problem_count, 0)
        self.assertEqual(catalog["photos"][0]["id"], "manual-id")
        self.assertEqual(catalog["photos"][0]["caption"], "Manual caption")
        self.assertNotIn("ignoredExecutable", catalog["photos"][0])

    def test_numeric_filename_caption_uses_friendly_oregon_summer_time(self):
        write_bytes(self.public / "sample_photos" / "20260711_173358.jpg", b"\xff\xd8\xff\xd9")

        catalog, result = refresh_photos.build_catalog(self.public)

        self.assertEqual(catalog["photos"][0]["caption"], "11 Jul 2026, 5:33 PM")
        self.assertEqual(catalog["photos"][0]["alt"], "11 Jul 2026, 5:33 PM")

    def test_numeric_filename_caption_uses_friendly_oregon_winter_time(self):
        write_bytes(self.public / "sample_photos" / "20261211_073358.jpg", b"\xff\xd8\xff\xd9")

        catalog, result = refresh_photos.build_catalog(self.public)

        self.assertEqual(catalog["photos"][0]["caption"], "11 Dec 2026, 7:33 AM")

    def test_numeric_filename_caption_prefers_exif_offset_when_available(self):
        write_bytes(
            self.public / "sample_photos" / "20260711_173358.jpg",
            sample_jpeg_with_exif("2026:07:11 20:33:58", "-04:00"),
        )

        catalog, result = refresh_photos.build_catalog(self.public)

        self.assertEqual(catalog["photos"][0]["caption"], "11 Jul 2026, 8:33 PM")

    def test_manual_and_nonnumeric_captions_are_preserved(self):
        write_bytes(self.public / "sample_photos" / "20260711_173358.jpg", b"\xff\xd8\xff\xd9")
        write_bytes(self.public / "sample_photos" / "camp-lights.jpg", b"\xff\xd8\xff\xd9")
        write_text(
            self.public / "photo_overrides.json",
            json.dumps({"photos": [{"image": "sample_photos/20260711_173358.jpg", "caption": "Manual time"}]}),
        )

        catalog, result = refresh_photos.build_catalog(self.public)
        captions = {photo["image"]: photo["caption"] for photo in catalog["photos"]}

        self.assertEqual(captions["sample_photos/20260711_173358.jpg"], "Manual time")
        self.assertEqual(captions["sample_photos/camp-lights.jpg"], "Camp Lights")

    def test_title_markdown_parses_standard_album_structure(self):
        title, errors = refresh_photos.parse_title_markdown(
            "# Trail album\n## Day one\n\nFirst paragraph.\nwraps here.\n\nSecond.\n"
        )

        self.assertEqual(errors, [])
        self.assertEqual(
            title,
            {
                "schemaVersion": 1,
                "title": "Trail album",
                "subtitle": "Day one",
                "paragraphs": ["First paragraph. wraps here.", "Second."],
            },
        )

    def test_missing_or_malformed_title_blocks_refresh(self):
        write_bytes(self.public / "sample_photos" / "plain.svg", b"<svg></svg>")

        with mock.patch.object(refresh_photos, "ROOT", Path(self.tmp.name)):
            with contextlib.redirect_stdout(io.StringIO()):
                missing_code = refresh_photos.refresh(self.public)

        write_text(Path(self.tmp.name) / "title.md", "## Subtitle without title\n")
        with mock.patch.object(refresh_photos, "ROOT", Path(self.tmp.name)):
            with contextlib.redirect_stdout(io.StringIO()):
                malformed_code = refresh_photos.refresh(self.public)

        self.assertEqual(missing_code, 1)
        self.assertEqual(malformed_code, 1)

    def test_refresh_writes_generated_public_title_data(self):
        write_bytes(self.public / "sample_photos" / "plain.svg", b"<svg></svg>")
        write_text(Path(self.tmp.name) / "title.md", "# Trail album\n\nShared from title.md.\n")

        with mock.patch.object(refresh_photos, "ROOT", Path(self.tmp.name)):
            with contextlib.redirect_stdout(io.StringIO()):
                code = refresh_photos.refresh(self.public)

        self.assertEqual(code, 0)
        self.assertEqual(
            json.loads((self.public / "title.json").read_text(encoding="utf-8")),
            {"schemaVersion": 1, "paragraphs": ["Shared from title.md."], "subtitle": "", "title": "Trail album"},
        )

    def test_missing_exif_and_gps_are_reported_without_blocking_svg(self):
        write_bytes(self.public / "sample_photos" / "plain.jpg", b"\xff\xd8\xff\xd9")
        write_bytes(self.public / "sample_photos" / "plain.svg", b"<svg></svg>")
        write_bytes(self.public / "sample_photos" / "note.txt", b"skip")

        catalog, result = refresh_photos.build_catalog(self.public)

        self.assertEqual(len(catalog["photos"]), 2)
        self.assertIn("plain.jpg", result.missing_date)
        self.assertIn("plain.jpg", result.missing_gps)
        self.assertIn("plain.svg", result.missing_date)
        self.assertIn("plain.svg", result.missing_gps)
        self.assertEqual(result.unsupported, ["note.txt"])

    def test_malformed_overrides_block_publishing(self):
        write_bytes(self.public / "sample_photos" / "plain.svg", b"<svg></svg>")
        write_text(self.public / "photo_overrides.json", "{bad json")

        with contextlib.redirect_stdout(io.StringIO()):
            code = refresh_photos.refresh(self.public)

        self.assertEqual(code, 1)
        self.assertFalse((self.public / "photos.json").exists())

    def test_dry_run_reports_change_without_replacing_catalog(self):
        write_bytes(self.public / "sample_photos" / "plain.svg", b"<svg></svg>")
        write_text(self.public / "photos.json", '{"old": true}\n')

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = refresh_photos.refresh(self.public, check=True)

        self.assertEqual(code, 1)
        self.assertEqual((self.public / "photos.json").read_text(encoding="utf-8"), '{"old": true}\n')
        self.assertIn("Check failed: generated public data would change.", output.getvalue())

    def test_repeated_refresh_is_deterministic_and_second_run_unchanged(self):
        write_bytes(self.public / "sample_photos" / "b.svg", b"<svg></svg>")
        write_bytes(self.public / "sample_photos" / "a.svg", b"<svg></svg>")

        with contextlib.redirect_stdout(io.StringIO()):
            first = refresh_photos.refresh(self.public)
        first_content = (self.public / "photos.json").read_bytes()
        first_title_content = (self.public / "title.json").read_bytes()
        with contextlib.redirect_stdout(io.StringIO()):
            second = refresh_photos.refresh(self.public)
        second_content = (self.public / "photos.json").read_bytes()
        second_title_content = (self.public / "title.json").read_bytes()

        self.assertEqual(first, 0)
        self.assertEqual(second, 0)
        self.assertEqual(first_content, second_content)
        self.assertEqual(first_title_content, second_title_content)

    def test_new_catalog_is_world_readable_for_static_hosting(self):
        write_bytes(self.public / "sample_photos" / "plain.svg", b"<svg></svg>")

        with contextlib.redirect_stdout(io.StringIO()):
            code = refresh_photos.refresh(self.public)

        self.assertEqual(code, 0)
        self.assertEqual(os.stat(self.public / "photos.json").st_mode & 0o777, 0o644)

    def test_atomic_write_failure_preserves_existing_catalog(self):
        write_bytes(self.public / "sample_photos" / "plain.svg", b"<svg></svg>")
        write_text(self.public / "photos.json", '{"old": true}\n')

        with mock.patch.object(refresh_photos, "atomic_write", side_effect=OSError("disk full")):
            with contextlib.redirect_stderr(io.StringIO()):
                code = refresh_photos.main(["--public-dir", str(self.public)])

        self.assertEqual(code, 1)
        self.assertEqual((self.public / "photos.json").read_text(encoding="utf-8"), '{"old": true}\n')


if __name__ == "__main__":
    unittest.main()
