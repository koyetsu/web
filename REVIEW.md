# Code Review Suggestions

## 1. Harden admin authentication
* Hash the admin password instead of storing it as plaintext in the `settings` table, and require the default to be rotated on first login. The current implementation reads and writes the password value directly, so anyone with database access can recover it and the default remains active indefinitely.【F:app.py†L37-L97】
* Consider refusing to start the app if `SECRET_KEY` is left at the default so session cookies remain protected in production deployments.【F:app.py†L25-L30】

## 2. Tighten upload handling
* The media upload path accepts any file type and saves it verbatim. Introduce an allow-list of MIME types/extensions, enforce size limits, and store files under generated names to avoid collisions or executable uploads that could be served back to users.【F:app.py†L187-L199】

## 3. Add safer content editing workflow
* `update_content_from_form` persists edits immediately to the live content row in the database, so a typo instantly affects the public site. Providing a draft/preview mode or version history would let admins review changes, roll back mistakes, and collaborate more safely.【F:app.py†L118-L128】【F:app.py†L281-L360】

## 4. Improve mobile experience controls
* `should_use_mobile_alt` relies solely on User-Agent sniffing and cannot be overridden once detected. Consider a persistent user preference (cookie or query param) so users can opt out of the mobile template, and expand detection to cover modern tablet UAs more accurately.【F:app.py†L332-L361】
