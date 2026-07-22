from html.parser import HTMLParser
import json
import socket
import subprocess
import sys
import time
from pathlib import Path
import re
import unittest

from playwright.sync_api import sync_playwright


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

        self.assertEqual(
            parser.links,
            [
                "https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css",
                "styles.css?v=viewer-20260722-nav",
            ],
        )
        self.assertEqual(
            parser.scripts,
            [
                "https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js",
                "app.js?v=viewer-20260722-nav",
            ],
        )
        for element_id in {
            "albumTitle",
            "albumSubtitle",
            "albumDescription",
            "thumbnailList",
            "previousPhoto",
            "nextPhoto",
            "mainPhoto",
            "photoCaption",
            "regionalMap",
            "localMap",
            "galleryShell",
            "toggleTripPanel",
            "toggleMapPanel",
            "photoFrame",
            "openViewer",
            "viewerControls",
            "viewerPreviousPhoto",
            "viewerNextPhoto",
            "zoomOutPhoto",
            "fitPhoto",
            "zoomInPhoto",
            "zoomLevel",
            "photoCounter",
            "restoreGallery",
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
            "title.json",
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
        self.assertIn('const assetVersion = "viewer-20260722-nav";', app)
        self.assertIn("const catalogUrl = `photos.json?v=${assetVersion}`;", app)
        self.assertIn("const titleUrl = `title.json?v=${assetVersion}`;", app)
        self.assertIn("await fetch(catalogUrl", app)
        self.assertIn("await loadAlbumTitle()", app)
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
            "updatePhotoCounter();",
            "scrollSelectedThumbnailIntoView();",
            "fitViewerImage();",
            "photoFrame.scrollTo({ top: 0, left: 0, behavior: \"auto\" });",
            "updateLocalMapView(photo);",
            "updateMapMarkerState();",
            'button.classList.toggle("is-selected", isSelected);',
            'button.setAttribute("aria-current", "true");',
            'button.removeAttribute("aria-current");',
            "marker.setIcon(createMarkerIcon(isSelected));",
            "marker.setZIndexOffset(isSelected ? 1000 : 0);",
            "closeAllMarkerPopups();",
        }:
            self.assertIn(expected, app)
        self.assertIn("options.popup.openOn(options.mapState.instance);", app)
        self.assertIn("marker.popup = L.popup({", app)
        self.assertIn(".setContent(buildMarkerPopupContent(photo));", app)
        self.assertIn("mapState.instance.closePopup();", app)

    def test_leaflet_maps_use_topographic_tiles_and_attribution(self):
        app = (PUBLIC / "app.js").read_text(encoding="utf-8")

        for expected in {
            'L.map(mapState.elementId, {',
            'L.tileLayer("https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png", {',
            "maxZoom: 17,",
            "maxNativeZoom: 17,",
            "OpenStreetMap",
            'https://www.openstreetmap.org/copyright',
            "OpenTopoMap",
            "https://opentopomap.org",
            "https://creativecommons.org/licenses/by-sa/3.0/",
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

    def test_map_headings_hide_visible_coordinate_subheads(self):
        html = (PUBLIC / "index.html").read_text(encoding="utf-8")
        app = (PUBLIC / "app.js").read_text(encoding="utf-8")

        self.assertIn('<h2 id="regionalMapTitle">Regional Map</h2>', html)
        self.assertIn('<h2 id="localMapTitle">Local Map</h2>', html)
        self.assertNotIn("regionalCoordinates", html)
        self.assertNotIn("localCoordinates", html)
        self.assertIn("function formatDemoLocation(photo)", app)
        self.assertIn("const marker = L.marker([photo.lat, photo.lon], {", app)
        self.assertNotIn("toFixed(4)", app)

    def test_regional_map_fits_all_mapped_photos_with_padding_and_max_zoom(self):
        app = (PUBLIC / "app.js").read_text(encoding="utf-8")

        for expected in {
            "const regionalZoom = 10;",
            "const regionalMaxFitZoom = 11;",
            "const localZoom = 14;",
            'elementId: "regionalMap",',
            'elementId: "localMap",',
            "function mappedPhotos()",
            "return photos.filter(hasCoordinates);",
            "function fitRegionalMap()",
            "const bounds = L.latLngBounds(mapped.map((mappedPhoto) => [mappedPhoto.lat, mappedPhoto.lon]));",
            "padding: [28, 28],",
            "maxZoom: mapState.maxFitZoom",
            "window.addEventListener(\"resize\", fitRegionalMap);",
            "const mapResizeObserver = new ResizeObserver(fitRegionalMap);",
        }:
            self.assertIn(expected, app)

    def test_local_map_tracks_selected_mapped_photo(self):
        app = (PUBLIC / "app.js").read_text(encoding="utf-8")

        for expected in {
            "function updateLocalMapView(photo)",
            "maps.local.instance.setView(latLng, maps.local.zoom);",
            "maps.local.instance.invalidateSize();",
            "updateLocalMapView(photo);",
        }:
            self.assertIn(expected, app)

    def test_side_columns_have_independent_accessible_collapse_controls(self):
        html = (PUBLIC / "index.html").read_text(encoding="utf-8")
        app = (PUBLIC / "app.js").read_text(encoding="utf-8")
        styles = (PUBLIC / "styles.css").read_text(encoding="utf-8")

        for expected in {
            'id="toggleTripPanel"',
            'aria-controls="tripPanel"',
            'aria-label="Collapse album and thumbnails"',
            'id="toggleMapPanel"',
            'aria-controls="mapPanel"',
            'aria-label="Collapse maps"',
            'aria-expanded="true"',
        }:
            self.assertIn(expected, html)

        for expected in {
            "function setPanelCollapsed(side, isCollapsed)",
            '"is-left-collapsed"',
            '"is-right-collapsed"',
            'button.setAttribute("aria-expanded", expanded ? "true" : "false");',
            'isCollapsed ? "Show album and thumbnails" : "Collapse album and thumbnails"',
            'button.setAttribute("aria-label", isCollapsed ? "Show maps" : "Collapse maps");',
            "function initializePanelToggles()",
        }:
            self.assertIn(expected, app)

        for expected in {
            ".gallery-shell.is-left-collapsed",
            ".gallery-shell.is-right-collapsed",
            ".gallery-shell.is-left-collapsed.is-right-collapsed",
            ".gallery-shell.is-left-collapsed .trip-panel",
            ".gallery-shell.is-right-collapsed .map-panel",
            ".panel-toggle:focus-visible",
        }:
            self.assertIn(expected, styles)

    def test_restoring_right_column_refreshes_leaflet_layout(self):
        app = (PUBLIC / "app.js").read_text(encoding="utf-8")

        for expected in {
            "function refreshMapsAfterLayoutChange()",
            "mapState.instance.invalidateSize();",
            "fitRegionalMap();",
            "updateLocalMapView(photos[selectedIndex]);",
            "setTimeout(refreshMapsAfterLayoutChange, 0);",
        }:
            self.assertIn(expected, app)

    def test_leaflet_markers_are_rendered_and_select_matching_photos(self):
        app = (PUBLIC / "app.js").read_text(encoding="utf-8")

        for expected in {
            "function buildMapMarkers(mapState)",
            "const marker = L.marker([photo.lat, photo.lon], {",
            "keyboard: true,",
            "bubblingMouseEvents: false,",
            "icon: createMarkerIcon(false)",
            "marker.popup = L.popup({",
            'marker.on("click", (event) => {',
            "L.DomEvent.stop(event.originalEvent);",
            'selectPhoto(index, { mapState, popup: marker.popup });',
            "marker.addTo(mapState.instance);",
            "mapState.markers.set(photo.id, marker);",
            'mapState.instance.on("click", closeAllMarkerPopups);',
            'document.addEventListener("click", handleDocumentClick);',
        }:
            self.assertIn(expected, app)

    def test_map_markers_use_star_icons_with_visible_selected_state(self):
        app = (PUBLIC / "app.js").read_text(encoding="utf-8")
        styles = (PUBLIC / "styles.css").read_text(encoding="utf-8")

        for expected in {
            "function createMarkerIcon(isSelected)",
            'className: `photo-map-marker${isSelected ? " is-selected" : ""}`',
            "html: isSelected",
            'html: isSelected',
            "iconSize: isSelected ? [24, 24] : [18, 18],",
            "iconAnchor: isSelected ? [12, 12] : [9, 9]",
        }:
            self.assertIn(expected, app)

        for expected in {
            ".photo-map-circle",
            ".photo-map-star",
            "clip-path: polygon(",
            "background: #111827;",
            ".photo-map-marker.is-selected .photo-map-star",
            "background: #facc15;",
            "border: 2px solid #1f2937;",
            ".photo-marker-popup-caption",
            ".photo-counter",
            ".thumbnail-button.is-selected::after",
        }:
            self.assertIn(expected, styles)

    def test_removed_date_labels_are_absent_while_friendly_caption_remains(self):
        title = json.loads((PUBLIC / "title.json").read_text(encoding="utf-8"))
        catalog = json.loads((PUBLIC / "photos.json").read_text(encoding="utf-8"))
        app = (PUBLIC / "app.js").read_text(encoding="utf-8")

        self.assertEqual(title["title"], "Mt. Hood Photo Map")
        self.assertEqual(title["subtitle"], "")
        self.assertNotIn("July 2026", json.dumps(title))
        self.assertIn('photoCounter.textContent = `Photo ${selectedIndex + 1} of ${photos.length}`;', app)
        self.assertTrue(any(photo["caption"] == "9 Jul 2026, 10:44 AM" for photo in catalog["photos"]))
        self.assertTrue(any(photo["date"] == "2026-07-09" for photo in catalog["photos"]))

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

    def test_full_screen_viewer_has_accessible_controls(self):
        html = (PUBLIC / "index.html").read_text(encoding="utf-8")
        styles = (PUBLIC / "styles.css").read_text(encoding="utf-8")

        for expected in {
            'id="openViewer"',
            'aria-label="Expand selected photo full screen"',
            'id="viewerControls"',
            'aria-label="Full-screen photo controls"',
            'id="viewerPreviousPhoto"',
            'aria-label="Previous photo in full-screen viewer"',
            'id="viewerNextPhoto"',
            'aria-label="Next photo in full-screen viewer"',
            'id="zoomOutPhoto"',
            'aria-label="Zoom out selected photo"',
            'id="fitPhoto"',
            'aria-label="Fit image to viewer"',
            'id="zoomInPhoto"',
            'aria-label="Zoom in selected photo"',
            'id="restoreGallery"',
            'aria-label="Restore gallery layout"',
            'aria-live="polite"',
        }:
            self.assertIn(expected, html)

        for expected in {
            ".open-viewer-button:focus-visible",
            ".viewer-button:focus-visible",
            ".fit-button",
            ".viewer-button:disabled",
            ".photo-frame.is-viewer-open .viewer-controls",
            "@media (max-width: 900px)",
            "max-width: calc(100vw - 1rem);",
        }:
            self.assertIn(expected, styles)

    def test_full_screen_viewer_uses_native_api_with_fallback_and_escape_restore(self):
        app = (PUBLIC / "app.js").read_text(encoding="utf-8")

        for expected in {
            "async function openFullScreenViewer()",
            "if (photoFrame.requestFullscreen) {",
            "await photoFrame.requestFullscreen();",
            "setViewerOpen(true, false);",
            "setViewerOpen(true, true);",
            "async function restoreGalleryLayout()",
            "document.exitFullscreen",
            "document.addEventListener(\"fullscreenchange\", () => {",
            "function isKeyboardEditableTarget(event)",
            'typeof event.composedPath === "function" ? event.composedPath()[0] : event.target',
            "const target = pathTarget instanceof Element ? pathTarget : document.activeElement;",
            "function handleViewerKeyboardShortcuts(event)",
            'event.key === "ArrowLeft"',
            'event.key === "ArrowRight"',
            'event.key === "+" || event.key === "="',
            'event.key === "-" || event.key === "_"',
            "document.addEventListener(\"keydown\", handleViewerKeyboardShortcuts);",
            'if (event.key === "Escape" && viewerOpen) {',
            "restoreGalleryLayout();",
            "setTimeout(refreshMapsAfterLayoutChange, 0);",
        }:
            self.assertIn(expected, app)

    def test_full_screen_viewer_zoom_is_limited_and_image_only(self):
        app = (PUBLIC / "app.js").read_text(encoding="utf-8")
        styles = (PUBLIC / "styles.css").read_text(encoding="utf-8")

        for expected in {
            "const minViewerZoom = 1;",
            "const maxViewerZoom = 4;",
            "const viewerZoomStep = 0.5;",
            'mainPhoto.style.setProperty("--viewer-zoom", viewerZoom);',
            "zoomOutPhoto.disabled = viewerZoom <= minViewerZoom;",
            "zoomInPhoto.disabled = viewerZoom >= maxViewerZoom;",
            "Math.min(maxViewerZoom, Math.max(minViewerZoom, nextZoom));",
            "function fitViewerImage()",
            'photoFrame.scrollTo({ top: 0, left: 0, behavior: "auto" });',
            "zoomOutPhoto.addEventListener(\"click\", () => adjustViewerZoom(-1));",
            "fitPhoto.addEventListener(\"click\", fitViewerImage);",
            "zoomInPhoto.addEventListener(\"click\", () => adjustViewerZoom(1));",
            "viewerPreviousPhoto.addEventListener(\"click\", () => selectPhoto(selectedIndex - 1));",
            "viewerNextPhoto.addEventListener(\"click\", () => selectPhoto(selectedIndex + 1));",
        }:
            self.assertIn(expected, app)

        for expected in {
            ".photo-frame.is-viewer-open {",
            "overflow: auto;",
            "width: calc(100vw * var(--viewer-zoom, 1));",
            "height: calc((100vh - 5.75rem) * var(--viewer-zoom, 1));",
            "object-fit: contain;",
        }:
            self.assertIn(expected, styles)

class BrowserGalleryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._server_port = cls._find_free_port()
        cls._server = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "http.server",
                str(cls._server_port),
                "--bind",
                "127.0.0.1",
            ],
            cwd=PUBLIC,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        cls._base_url = f"http://127.0.0.1:{cls._server_port}/index.html"
        cls._wait_for_server()
        cls._playwright = sync_playwright().start()
        cls._browser = cls._playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls._browser.close()
        cls._playwright.stop()
        cls._server.terminate()
        try:
            cls._server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            cls._server.kill()

    @classmethod
    def _find_free_port(cls):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return sock.getsockname()[1]

    @classmethod
    def _wait_for_server(cls):
        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", cls._server_port), timeout=0.2):
                    return
            except OSError:
                time.sleep(0.1)
        raise RuntimeError("static server did not start")

    def setUp(self):
        self.page = self._browser.new_page(viewport={"width": 1440, "height": 1200})
        self.console_errors = []
        self.page_errors = []
        self.page.on("console", self._collect_console)
        self.page.on("pageerror", lambda error: self.page_errors.append(str(error)))

    def tearDown(self):
        self.page.close()

    def _collect_console(self, message):
        if message.type == "error":
            self.console_errors.append(message.text)

    def _load_app(self):
        catalog = json.loads((PUBLIC / "photos.json").read_text(encoding="utf-8"))
        total = len(catalog["photos"])
        self.page.goto(self._base_url, wait_until="load")
        self.page.wait_for_function(
            """(expected) => document.querySelector('#photoCounter')?.textContent === expected""",
            arg=f"Photo 1 of {total}",
        )
        self.page.wait_for_function(
            "() => document.querySelectorAll('.photo-map-marker').length > 0"
        )
        return catalog

    def _wait_for_counter(self, expected):
        self.page.wait_for_function(
            """(value) => document.querySelector('#photoCounter')?.textContent === value""",
            arg=expected,
        )

    def test_marker_hierarchy_popup_and_selection_are_synchronized(self):
        catalog = self._load_app()
        photos = catalog["photos"]
        total = len(photos)
        middle_index = total // 2
        no_gps_index = next(
            index for index, photo in enumerate(photos) if "lat" not in photo and "lon" not in photo
        )
        coord_count = sum(1 for photo in photos if "lat" in photo and "lon" in photo)

        self.assertEqual(self.page.locator(".leaflet-popup").count(), 0)
        self.assertEqual(self.page.locator(".thumbnail-button[aria-current='true']").count(), 1)
        self.assertEqual(self.page.locator(".photo-map-marker.is-selected").count(), 2)
        self.assertEqual(self.page.locator(".photo-map-star").count(), 2)
        self.assertEqual(self.page.locator(".photo-map-circle").count(), coord_count * 2 - 2)
        self.assertEqual(self.page.locator("#photoCounter").text_content(), f"Photo 1 of {total}")
        self.assertEqual(self.page.locator("#photoCaption").text_content(), photos[0]["caption"])

        selected_thumbnail = self.page.locator(".thumbnail-button[aria-current='true']")
        self.assertEqual(selected_thumbnail.evaluate("el => getComputedStyle(el).borderColor"), "rgb(11, 79, 74)")

        selected_marker_z = self.page.locator(".photo-map-marker.is-selected").first.evaluate(
            "el => Number.parseInt(el.style.zIndex || '0', 10)"
        )
        other_marker_z = self.page.locator(".photo-map-marker:not(.is-selected)").first.evaluate(
            "el => Number.parseInt(el.style.zIndex || '0', 10)"
        )
        self.assertGreater(selected_marker_z, other_marker_z)

        self.page.locator("#nextPhoto").click()
        self._wait_for_counter(f"Photo 2 of {total}")
        self.assertEqual(self.page.locator("#photoCaption").text_content(), photos[1]["caption"])

        self.page.locator("#previousPhoto").click()
        self._wait_for_counter(f"Photo 1 of {total}")
        self.assertEqual(self.page.locator(".thumbnail-button[aria-current='true']").count(), 1)

        self.page.locator(".thumbnail-button").nth(middle_index).click()
        self._wait_for_counter(f"Photo {middle_index + 1} of {total}")
        middle_has_coordinates = "lat" in photos[middle_index] and "lon" in photos[middle_index]
        self.assertEqual(
            self.page.locator(".photo-map-marker.is-selected").count(),
            2 if middle_has_coordinates else 0,
        )

        self.page.locator("#regionalMap .photo-map-marker").nth(1).dispatch_event("click")
        self._wait_for_counter(f"Photo 2 of {total}")
        self.page.wait_for_function("() => document.querySelectorAll('.leaflet-popup').length === 1")
        self.assertEqual(self.page.locator(".leaflet-popup").count(), 1)
        self.assertIn(photos[1]["caption"], self.page.locator(".leaflet-popup").text_content())

        self.page.locator("#regionalMap .photo-map-marker").nth(2).dispatch_event("click")
        self.page.wait_for_function("() => document.querySelectorAll('.leaflet-popup').length === 1")
        self.assertEqual(self.page.locator(".leaflet-popup").count(), 1)
        self.assertIn(photos[2]["caption"], self.page.locator(".leaflet-popup").text_content())

        self.page.locator("#regionalMap").click(position={"x": 320, "y": 260}, force=True)
        self.page.wait_for_function("() => document.querySelector('.leaflet-popup') === null")
        self.assertEqual(self.page.locator(".leaflet-popup").count(), 0)

        self.page.locator(".thumbnail-button").nth(total - 1).click()
        self._wait_for_counter(f"Photo {total} of {total}")
        self.assertEqual(self.page.locator(".photo-map-marker.is-selected").count(), 2)

        self.page.evaluate(
            """() => {
                const list = document.querySelector('.thumbnail-list');
                list.scrollTop = list.scrollHeight;
                window.scrollTo(0, 0);
            }"""
        )
        self.page.locator(".thumbnail-button").first.click()
        self._wait_for_counter("Photo 1 of {}".format(total))
        self.page.wait_for_function(
            "() => document.querySelector('.thumbnail-list').scrollTop < 40"
        )
        self.assertEqual(self.page.evaluate("window.scrollY"), 0)

        self.page.locator(".thumbnail-button").nth(no_gps_index).click()
        self._wait_for_counter(f"Photo {no_gps_index + 1} of {total}")
        self.assertEqual(self.page.locator(".photo-map-marker.is-selected").count(), 0)

        self.assertEqual(self.console_errors, [])
        self.assertEqual(self.page_errors, [])

    def test_viewer_keyboard_shortcuts_and_fit_reset_behavior(self):
        catalog = self._load_app()
        photos = catalog["photos"]
        total = len(photos)

        self.page.keyboard.press("ArrowLeft")
        self._wait_for_counter(f"Photo {total} of {total}")
        self.assertEqual(self.page.locator("#photoCaption").text_content(), photos[-1]["caption"])

        self.page.keyboard.press("ArrowRight")
        self._wait_for_counter("Photo 1 of {}".format(total))
        self.assertEqual(self.page.locator("#photoCaption").text_content(), photos[0]["caption"])

        self.page.locator("#openViewer").click()
        self.page.wait_for_function("() => document.querySelector('.photo-frame').classList.contains('is-viewer-open')")
        self.assertTrue(self.page.locator(".photo-frame").evaluate("el => el.classList.contains('is-viewer-open')"))
        self.assertEqual(self.page.locator("#zoomLevel").text_content(), "1x")

        self.page.keyboard.press("=")
        self.assertEqual(self.page.locator("#zoomLevel").text_content(), "1.5x")
        self.page.keyboard.press("+")
        self.assertEqual(self.page.locator("#zoomLevel").text_content(), "2x")
        self.page.keyboard.press("-")
        self.assertEqual(self.page.locator("#zoomLevel").text_content(), "1.5x")

        self.page.evaluate(
            """() => {
                const frame = document.querySelector('#photoFrame');
                frame.scrollTop = 200;
                frame.scrollLeft = 160;
            }"""
        )
        self.page.locator("#fitPhoto").click()
        self.assertEqual(self.page.locator("#zoomLevel").text_content(), "1x")
        self.assertTrue(self.page.locator("#zoomOutPhoto").is_disabled())
        self.assertFalse(self.page.locator("#zoomInPhoto").is_disabled())
        self.page.wait_for_function(
            "() => document.querySelector('#photoFrame').scrollTop === 0 && document.querySelector('#photoFrame').scrollLeft === 0"
        )

        for _ in range(6):
            if self.page.locator("#zoomInPhoto").is_disabled():
                break
            self.page.locator("#zoomInPhoto").click()
        self.assertEqual(self.page.locator("#zoomLevel").text_content(), "4x")
        self.assertTrue(self.page.locator("#zoomInPhoto").is_disabled())
        self.assertFalse(self.page.locator("#zoomOutPhoto").is_disabled())

        self.page.keyboard.press("ArrowRight")
        self.assertEqual(self.page.locator("#zoomLevel").text_content(), "1x")
        self.assertTrue(self.page.locator("#zoomOutPhoto").is_disabled())
        self.page.wait_for_function("() => document.querySelector('#photoFrame').scrollTop === 0")

        self.page.keyboard.press("Escape")
        self.page.wait_for_function("() => !document.querySelector('.photo-frame').classList.contains('is-viewer-open')")
        self.assertFalse(self.page.locator(".photo-frame").evaluate("el => el.classList.contains('is-viewer-open')"))

        self.page.evaluate(
            """() => {
                const input = document.createElement('input');
                input.id = 'keyboard-test-input';
                const textarea = document.createElement('textarea');
                textarea.id = 'keyboard-test-textarea';
                const select = document.createElement('select');
                select.id = 'keyboard-test-select';
                select.innerHTML = '<option>One</option><option>Two</option>';
                const editable = document.createElement('div');
                editable.id = 'keyboard-test-editable';
                editable.contentEditable = 'true';
                editable.textContent = 'Editable';
                document.body.append(input, textarea, select, editable);
            }"""
        )

        for control_id in {
            "keyboard-test-input",
            "keyboard-test-textarea",
            "keyboard-test-select",
            "keyboard-test-editable",
        }:
            self.assertTrue(
                self.page.evaluate(
                    """(id) => {
                        const control = document.getElementById(id);
                        return window.__tinyPhotoMapDebug.isKeyboardEditableTarget({
                            composedPath: () => [control],
                            target: control
                        });
                    }""",
                    control_id,
                )
            )

        self.page.locator("#openViewer").click()
        self.page.wait_for_function("() => document.querySelector('.photo-frame').classList.contains('is-viewer-open')")
        self.assertEqual(self.page.locator("#zoomLevel").text_content(), "1x")
        self.page.evaluate(
            """() => {
                const input = document.getElementById('keyboard-test-input');
                window.__tinyPhotoMapDebug.handleViewerKeyboardShortcuts({
                    composedPath: () => [input],
                    key: '=',
                    preventDefault() {}
                });
            }"""
        )
        self.assertEqual(self.page.locator("#zoomLevel").text_content(), "1x")
        self.page.evaluate(
            """() => {
                const input = document.getElementById('keyboard-test-input');
                window.__tinyPhotoMapDebug.handleViewerKeyboardShortcuts({
                    composedPath: () => [input],
                    key: '-',
                    preventDefault() {}
                });
            }"""
        )
        self.assertEqual(self.page.locator("#zoomLevel").text_content(), "1x")
        self.page.evaluate(
            """() => {
                const input = document.getElementById('keyboard-test-input');
                window.__tinyPhotoMapDebug.handleViewerKeyboardShortcuts({
                    composedPath: () => [input],
                    key: 'Escape',
                    preventDefault() {}
                });
            }"""
        )
        self.page.wait_for_function("() => !document.querySelector('.photo-frame').classList.contains('is-viewer-open')")

        self.assertEqual(self.console_errors, [])
        self.assertEqual(self.page_errors, [])


if __name__ == "__main__":
    unittest.main()
