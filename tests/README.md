# Tests

Lightweight automated checks for the static gallery belong here. The tests validate `public/` because it is the live source served at `/pics/`.

Run the current checks with:

```sh
python -m unittest tests/test_static_gallery.py tests/test_refresh_photos.py
```
