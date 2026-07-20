# Tiny Photo Map

Tiny Photo Map is a deliberately small static photo gallery for sharing one trip at a time.

The intended page has three fixed areas:

1. A left column with the trip title and a vertically scrolling thumbnail list.
2. A fixed middle area showing the selected photo, with its caption and previous/next arrows at the top.
3. A fixed right column with two maps for the selected photo: one regional view and one close-up view.

## First milestone

The first milestone is one local static gallery using local sample images and manually supplied photo metadata. It should not include uploads, accounts, a database, video, search, tagging, deployment automation, or automatic EXIF scanning.

## Public gallery

The live static site source is `public/`. Caddy serves this directory directly at:

```text
https://hike.cyclewriter.com/pics/
```

Approved changes to files under `public/` are live as soon as they are saved. There is no rsync step, deployment script, build command, or Git operation required for publishing.

Open `public/index.html` in a browser to view the current static shell locally. It selects the first sample photo on load, supports thumbnail selection and previous/next arrows, and updates two Leaflet maps using manually supplied coordinates and OpenStreetMap tiles.

Run the focused local check with:

```sh
python -m unittest tests/test_static_gallery.py
```

## Planned project folders

- `public/` — live static site source served at `/pics/`
- `public/sample_photos/` — public sample images used by the live gallery
- `gallery/` — original development copy retained for reference
- `sample_photos/` — original sample images retained for reference
- `scripts/` — small build or validation helpers
- `tests/` — lightweight automated checks
- `docs/` — approved layout and project boundaries

Personal photo collections should not be committed to GitHub.
