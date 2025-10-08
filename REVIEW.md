# Code Review Suggestions

## 1. Harden admin authentication
* Hash the admin password instead of storing it as plaintext in the `settings` table, and require the default to be rotated on first login. The current implementation reads and writes the password value directly, so anyone with database access can recover it and the default remains active indefinitely.【F:app.py†L88-L109】
* Consider refusing to start the app if `SECRET_KEY` is left at the default so session cookies remain protected in production deployments.【F:app.py†L28-L33】

## 2. Tighten upload handling
* The media upload path accepts any file type and saves it verbatim. Introduce an allow-list of MIME types/extensions, enforce size limits, and store files under generated names to avoid collisions or executable uploads that could be served back to users.【F:app.py†L524-L533】

## 3. Expand draft safety controls
* Admin mode now persists unsaved edits in a shared `drafts` table keyed only by the session cookie. Consider adding automatic cleanup for abandoned drafts, per-user identifiers, or change history so concurrent editors don't overwrite each other and operators can revert to prior revisions if a draft is accidentally saved.【F:app.py†L152-L213】【F:app.py†L560-L590】

## 4. Improve mobile experience controls
* `should_use_mobile_alt` relies solely on User-Agent sniffing and cannot be overridden once detected. Consider a persistent user preference (cookie or query param) so users can opt out of the mobile template, and expand detection to cover modern tablet UAs more accurately.【F:app.py†L614-L629】
