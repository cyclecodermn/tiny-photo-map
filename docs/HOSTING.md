# Hosting

Tiny Photo Map is hosted as static files.

## Live Source

The live source of truth is:

```text
/home/steven/dev/tiny-photo-map/public/
```

The public URL is:

```text
https://hike.cyclewriter.com/pics/
```

When Caddy has the `/pics/` route installed, saving an approved file under `public/` changes the live static site immediately. Publishing must not require rsync, a deployment script, a build framework, a package manager, or Git operations.

## Caddy Route

The intended path-scoped route inside the existing `hike.cyclewriter.com` site is:

```caddyfile
handle_path /pics/* {
	root * /home/steven/dev/tiny-photo-map/public
	file_server
}
```

Keep the existing `hike.cyclewriter.com` root and unrelated routes unchanged.

The previous copied directory at `/srv/www/default-site/public/hike/pics` should remain in place until the direct route is accepted and rollback material is no longer needed.
