# Scripts

Small build and validation helpers belong here. Keep them narrow and easy to run from the command line.

Publishing does not belong here. The live `/pics/` route serves `public/` directly, so no deployment script, rsync command, or Git operation is required to update approved static files.

Refresh the generated photo catalog after copying JPG or JPEG files into `public/sample_photos/`:

```sh
python scripts/refresh_photos.py
```

Use `--check` to report whether `public/photos.json` would change without replacing it.
