# Gallery

This folder contains the first static Tiny Photo Map gallery shell and is retained as a development reference.

The live source of truth is `../public/`, which Caddy serves directly at `/pics/`.

Open `../public/index.html` in a browser to view the local sample trip. The page is build-free and uses:

- `index.html` for the three-column shell
- `styles.css` for the fixed gallery layout
- `photos.js` for manually entered sample photo metadata
- `app.js` for thumbnail selection, arrow navigation, and Leaflet map updates

The maps load Leaflet from a public CDN and use the standard OpenStreetMap tile layer with visible OpenStreetMap attribution.
