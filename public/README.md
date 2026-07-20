# Public Site

This directory is the live Tiny Photo Map source of truth for `/pics/`.

Caddy serves this directory directly. Save approved static files here to update the public site; no rsync, deployment script, build step, or Git operation is part of publishing.

Required files:

- `index.html`
- `styles.css`
- `photos.json`
- `photo_overrides.json`
- `app.js`
- `sample_photos/`

Keep the site self-contained by using relative paths inside `public/`.

Refresh `photos.json` after copying JPG or JPEG files into `sample_photos/`:

```sh
python ../scripts/refresh_photos.py
```

Edit `photo_overrides.json` for manual captions, corrected dates, coordinates, alt text, and SVG demonstration metadata.
