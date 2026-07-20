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
            "regionalCoordinates",
            "localCoordinates",
        }:
            self.assertIn(element_id, parser.ids)

    def test_photo_data_uses_local_samples_with_portland_demo_coordinates(self):
        photo_data = (GALLERY / "photos.js").read_text(encoding="utf-8")
        ids = re.findall(r'id: "([^"]+)"', photo_data)
        images = re.findall(r'image: "([^"]+)"', photo_data)
        coordinates = re.findall(r"lat: (-?\d+\.\d+),\n    lon: (-?\d+\.\d+)", photo_data)
        demo_locations = re.findall(r'demoLocation: "([^"]+)"', photo_data)

        self.assertEqual(len(ids), 4)
        self.assertEqual(len(images), len(ids))
        self.assertEqual(len(coordinates), len(ids))
        self.assertEqual(len(demo_locations), len(ids))
        self.assertIn(("45.4659", "-122.6630"), coordinates)
        self.assertIn(("45.5117", "-122.5947"), coordinates)
        self.assertIn(("45.5884", "-122.7641"), coordinates)
        self.assertIn("Sellwood Riverfront Park", demo_locations)
        self.assertIn("Mount Tabor Park", demo_locations)
        self.assertIn("Cathedral Park", demo_locations)
        self.assertIn("Demonstration data only", photo_data)
        self.assertNotIn("Three Sisters", photo_data)
        for image in images:
            self.assertTrue(image.startswith("../sample_photos/"))
            self.assertTrue((GALLERY / image).resolve().is_file())

    def test_first_photo_is_selected_on_load(self):
        app = (GALLERY / "app.js").read_text(encoding="utf-8")

        self.assertIn("selectPhoto(0);", app)
        self.assertIn('button.addEventListener("click", () => selectPhoto(index));', app)
        self.assertIn('previousPhoto.addEventListener("click"', app)
        self.assertIn('nextPhoto.addEventListener("click"', app)

    def test_selection_updates_photo_thumbnail_and_map_state(self):
        app = (GALLERY / "app.js").read_text(encoding="utf-8")

        for expected in {
            "mainPhoto.src = photo.image;",
            "mainPhoto.alt = photo.alt;",
            "photoCaption.textContent = photo.caption;",
            "photoDate.textContent = photo.date;",
            "regionalCoordinates.textContent = formatDemoLocation(photo);",
            "localCoordinates.textContent = formatDemoLocation(photo);",
            "updateMapMarkerState();",
            'button.classList.toggle("is-selected", isSelected);',
            'button.setAttribute("aria-current", isSelected ? "true" : "false");',
            'marker.classList.toggle("is-selected", isSelected);',
        }:
            self.assertIn(expected, app)

    def test_map_markers_are_rendered_and_select_matching_photos(self):
        app = (GALLERY / "app.js").read_text(encoding="utf-8")

        for expected in {
            'buildMapMarkers(regionalMarker, "regionalPosition");',
            'buildMapMarkers(localMarker, "localPosition");',
            'marker.className = "map-marker";',
            "marker.dataset.photoId = photo.id;",
            'marker.addEventListener("click", () => selectPhoto(index));',
            "moveMarker(marker, position);",
        }:
            self.assertIn(expected, app)

    def test_photos_without_coordinates_are_supported(self):
        app = (GALLERY / "app.js").read_text(encoding="utf-8")

        for expected in {
            "function hasCoordinates(photo)",
            "return Number.isFinite(photo.lat) && Number.isFinite(photo.lon);",
            'const noDemoCoordinatesText = "No demonstration coordinates for this photo";',
            "if (!hasCoordinates(photo)) {",
            "if (!hasCoordinates(photo) || !position) {",
        }:
            self.assertIn(expected, app)

    def test_selected_photo_fills_frame_without_cropping(self):
        styles = (GALLERY / "styles.css").read_text(encoding="utf-8")

        image_rule = re.search(r"\.photo-frame img \{(?P<body>[^}]+)\}", styles)
        self.assertIsNotNone(image_rule)
        rule_body = image_rule.group("body")

        for expected in {
            "width: 100%;",
            "height: 100%;",
            "max-width: 100%;",
            "max-height: 100%;",
            "object-fit: contain;",
        }:
            self.assertIn(expected, rule_body)


if __name__ == "__main__":
    unittest.main()
