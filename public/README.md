# Public Site

This directory is the live Tiny Photo Map source of truth for `/pics/`.

Caddy serves this directory directly. Save approved static files here to update the public site; no rsync, deployment script, build step, or Git operation is part of publishing.

Required files:

- `index.html`
- `styles.css`
- `photos.js`
- `app.js`
- `sample_photos/`

Keep the site self-contained by using relative paths inside `public/`.
