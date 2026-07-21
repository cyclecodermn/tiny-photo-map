from html.parser import HTMLParser
import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"


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
        parser.feed((PUBLIC / "index.html").read_text(encoding="utf-8"))

        self.assertEqual(parser.links, ["https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css", "styles.css"])
        self.assertEqual(
            parser.scripts,
            ["https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js", "app.js"],
        )
        for element_id in {
            "thumbnailList",
            "previousPhoto",
            "nextPhoto",
            "mainPhoto",
            "photoCaption",
            "regionalMap",
            "localMap",
            "regionalCoordinates",
            "localCoordinates",
        }:
            self.assertIn(element_id, parser.ids)

    def test_photo_data_uses_local_samples_with_real_photo_coordinates(self):
        catalog = json.loads((PUBLIC / "photos.json").read_text(encoding="utf-8"))
        photos = catalog["photos"]
        ids = [photo["id"] for photo in photos]
        images = [photo["image"] for photo in photos]
        mapped_photos = [
            photo
            for photo in photos
            if isinstance(photo.get("lat"), int | float) and isinstance(photo.get("lon"), int | float)
        ]
        photo_data = json.dumps(catalog)

        self.assertEqual(catalog["schemaVersion"], 1)
        self.assertGreaterEqual(len(ids), 1)
        self.assertEqual(len(images), len(ids))
        self.assertGreaterEqual(len(mapped_photos), 1)
        self.assertTrue(
            any(
                -90 <= photo["lat"] <= 90 and -180 <= photo["lon"] <= 180
                for photo in mapped_photos
            )
        )
        self.assertIn("sample_photos/20260709_153020.jpg", images)
        self.assertFalse(
            any(
                "lat" in photo or "lon" in photo
                for photo in photos
                if photo["image"] == "sample_photos/20260709_153020.jpg"
            )
        )
        self.assertNotIn("Demonstration data only", photo_data)
        self.assertNotIn("regionalPosition", photo_data)
        self.assertNotIn("localPosition", photo_data)
        for image in images:
            self.assertTrue(image.startswith("sample_photos/"))
            self.assertTrue(image.lower().endswith((".jpg", ".jpeg")))
            self.assertTrue((PUBLIC / image).resolve().is_file())

    def test_public_site_is_self_contained(self):
        required_assets = {
            "index.html",
            "styles.css",
            "photos.json",
            "photo_overrides.json",
            "app.js",
        }
        catalog = json.loads((PUBLIC / "photos.json").read_text(encoding="utf-8"))
        catalog_images = {photo["image"] for photo in catalog["photos"]}

        for asset in required_assets | catalog_images:
            self.assertTrue((PUBLIC / asset).is_file(), asset)

        photo_data = (PUBLIC / "photos.json").read_text(encoding="utf-8")
        self.assertNotIn("../sample_photos/", photo_data)

    def test_first_photo_is_selected_on_load(self):
        app = (PUBLIC / "app.js").read_text(encoding="utf-8")

        self.assertIn("selectPhoto(0);", app)
        self.assertIn('const catalogUrl = "photos.json";', app)
        self.assertIn("await fetch(catalogUrl", app)
        self.assertNotIn("window.tinyPhotoMapPhotos", app)
        self.assertIn('button.addEventListener("click", () => selectPhoto(index));', app)
        self.assertIn('previousPhoto.addEventListener("click"', app)
        self.assertIn('nextPhoto.addEventListener("click"', app)

    def test_selection_updates_photo_thumbnail_and_map_state(self):
        app = (PUBLIC / "app.js").read_text(encoding="utf-8")

        for expected in {
            "mainPhoto.src = photo.image;",
            'mainPhoto.alt = safeText(photo.alt, safeText(photo.caption, "Trip photo"));',
            "photoCaption.textContent = safeText(photo.caption, photo.image);",
            'photoDate.textContent = safeText(photo.date, "Date unavailable");',
            "regionalCoordinates.textContent = formatDemoLocation(photo);",
            "localCoordinates.textContent = formatDemoLocation(photo);",
            "updateMapViews(photo);",
            "updateMapMarkerState();",
            'button.classList.toggle("is-selected", isSelected);',
            'button.setAttribute("aria-current", isSelected ? "true" : "false");',
            "marker.setIcon(createMarkerIcon(isSelected));",
            "marker.openPopup();",
        }:
            self.assertIn(expected, app)

    def test_leaflet_maps_use_openstreetmap_tiles_and_attribution(self):
        app = (PUBLIC / "app.js").read_text(encoding="utf-8")

        for expected in {
            'L.map(mapState.elementId, {',
            'L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {',
            "maxZoom: 19,",
            "OpenStreetMap",
            'https://www.openstreetmap.org/copyright',
            "tiles.on(\"tileerror\", () => {",
            "tiles.addTo(mapState.instance);",
            "scrollWheelZoom: false",
            "setTimeout(() => mapState.instance.invalidateSize(), 0);",
        }:
            self.assertIn(expected, app)

    def test_old_illustrated_mock_map_is_absent(self):
        public_text = "\n".join(
            (PUBLIC / name).read_text(encoding="utf-8")
            for name in {"index.html", "styles.css", "photos.json", "app.js"}
        )

        for old_mock_map_marker in {
            "mock-map",
            "regionalPosition",
            "localPosition",
        }:
            self.assertNotIn(old_mock_map_marker, public_text)

    def test_both_map_instances_have_fixed_zoom_levels(self):
        app = (PUBLIC / "app.js").read_text(encoding="utf-8")

        for expected in {
            "const regionalZoom = 10;",
            "const localZoom = 14;",
            'elementId: "regionalMap",',
            'elementId: "localMap",',
            "mapState.instance.setView(latLng, mapState.zoom);",
        }:
            self.assertIn(expected, app)

    def test_leaflet_markers_are_rendered_and_select_matching_photos(self):
        app = (PUBLIC / "app.js").read_text(encoding="utf-8")

        for expected in {
            "function buildMapMarkers(mapState)",
            "const marker = L.marker([photo.lat, photo.lon], {",
            "keyboard: true,",
            "icon: createMarkerIcon(false)",
            'marker.on("click", () => selectPhoto(index));',
            "marker.addTo(mapState.instance);",
            "mapState.markers.set(photo.id, marker);",
        }:
            self.assertIn(expected, app)

    def test_photos_without_coordinates_are_supported(self):
        app = (PUBLIC / "app.js").read_text(encoding="utf-8")

        for expected in {
            "function hasCoordinates(photo)",
            "return Number.isFinite(photo.lat) && Number.isFinite(photo.lon);",
            'const noDemoCoordinatesText = "No demonstration coordinates for this photo";',
            "if (!hasCoordinates(photo)) {",
            "const firstMappedPhoto = photos.find(hasCoordinates);",
            "if (!firstMappedPhoto) {",
            "No photo coordinates are available. The gallery remains available.",
        }:
            self.assertIn(expected, app)

    def test_catalog_load_failures_show_useful_gallery_messages(self):
        app = (PUBLIC / "app.js").read_text(encoding="utf-8")

        for expected in {
            "function showGalleryMessage(message)",
            "Photo catalog could not load.",
            "photos.json must contain a photos array.",
            "No photos found in the catalog.",
            "previousPhoto.disabled = true;",
            "nextPhoto.disabled = true;",
        }:
            self.assertIn(expected, app)

    def test_map_fallbacks_are_visible_without_breaking_gallery(self):
        html = (PUBLIC / "index.html").read_text(encoding="utf-8")
        app = (PUBLIC / "app.js").read_text(encoding="utf-8")

        for expected in {
            'class="map-fallback" data-map-fallback="regional" hidden',
            'class="map-fallback" data-map-fallback="local" hidden',
            "Map library could not load. The gallery and selected photo details remain available.",
            "Map tiles could not load. The gallery and selected photo details remain available.",
            "if (!window.L) {",
        }:
            self.assertTrue(expected in html or expected in app)

    def test_selected_photo_fills_frame_without_cropping(self):
        styles = (PUBLIC / "styles.css").read_text(encoding="utf-8")

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
