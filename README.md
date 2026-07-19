# Tiny Photo Map

Tiny Photo Map is a deliberately small static photo gallery for sharing one trip at a time.

The intended page has three fixed areas:

1. A left column with the trip title and a vertically scrolling thumbnail list.
2. A fixed middle area showing the selected photo, with its caption and previous/next arrows at the top.
3. A fixed right column with two maps for the selected photo: one regional view and one close-up view.

## First milestone

The first milestone is one local static gallery using local sample images and manually supplied photo metadata. It should not include uploads, accounts, a database, video, search, tagging, deployment automation, or automatic EXIF scanning.

## Planned project folders

- `gallery/` — static gallery files
- `sample_photos/` — a few non-personal sample images used for development
- `scripts/` — small build or validation helpers
- `tests/` — lightweight automated checks
- `docs/` — approved layout and project boundaries

Personal photo collections should not be committed to GitHub.
