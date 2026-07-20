from html.parser import HTMLParser
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
GALLERY = ROOT / "gallery"
SAMPLES = ROOT / "sample_photos"


class GalleryParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.scripts = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.add(attrs["id"])
        if tag == "script" and "src" in attrs:
            self.scripts.append(attrs["src"])
        if tag == "link" and attrs.get("rel") == "stylesheet":
            self.links.append(attrs.get("href"))


class StaticGalleryTest(unittest.TestCase):
    def test_shell_has_expected_static_assets_and_controls(self):
        parser = GalleryParser()
        parser.feed((GALLERY / "index.html").read_text(encoding="utf-8"))

        self.assertEqual(parser.links, ["styles.css"])
        self.assertEqual(parser.scripts, ["photos.js", "app.js"])
        for element_id in {
            "thumbnailList",
            "previousPhoto",
            "nextPhoto",
            "mainPhoto",
            "photoCaption",
            "regionalMarker",
            "localMarker",
        }:
            self.assertIn(element_id, parser.ids)

    def test_photo_data_uses_local_samples_with_manual_coordinates(self):
        photo_data = (GALLERY / "photos.js").read_text(encoding="utf-8")
        ids = re.findall(r'id: "([^"]+)"', photo_data)
        images = re.findall(r'image: "([^"]+)"', photo_data)
        coordinates = re.findall(r"lat: (-?\d+\.\d+),\n    lon: (-?\d+\.\d+)", photo_data)

        self.assertEqual(len(ids), 4)
        self.assertEqual(len(images), len(ids))
        self.assertEqual(len(coordinates), len(ids))
        for image in images:
            self.assertTrue(image.startswith("../sample_photos/"))
            self.assertTrue((GALLERY / image).resolve().is_file())

    def test_first_photo_is_selected_on_load(self):
        app = (GALLERY / "app.js").read_text(encoding="utf-8")

        self.assertIn("selectPhoto(0);", app)
        self.assertIn('button.addEventListener("click", () => selectPhoto(index));', app)
        self.assertIn('previousPhoto.addEventListener("click"', app)
        self.assertIn('nextPhoto.addEventListener("click"', app)


if __name__ == "__main__":
    unittest.main()
