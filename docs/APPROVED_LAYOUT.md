# Approved Initial Layout

The first Tiny Photo Map page should remain intentionally simple.

## Desktop layout

### Left column

- Trip title and short trip information at the top.
- A vertical list of photo thumbnails below it.
- Only the thumbnail list scrolls.
- Selecting a thumbnail changes the main photo and both map markers.

### Middle column

- Fixed in place and fills the available middle area.
- Caption and photo date appear at the top.
- Previous and next controls are simple left and right arrows.
- The selected photo fills the remaining area without cropping important content.

### Right column

- Fixed in place.
- Upper map shows the selected photo in a wider regional context.
- Lower map shows a closer local view.
- Both maps update when the selected photo changes.

## First milestone limits

Include only:

- one trip
- local sample images
- thumbnail selection
- arrow navigation
- captions and dates
- manually supplied latitude and longitude
- two location-aware map views

Do not include:

- uploads through the site
- accounts or user management
- a database
- video
- search or tagging
- photo editing
- automatic EXIF scanning
- VPS deployment
- changes to Photoview

The site should remain understandable as ordinary static files with a small amount of JavaScript.

The live public version belongs under `public/` and should remain self-contained so Caddy can serve `/pics/` directly from the project.
