# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.0.x   | Yes       |

## Reporting a vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

Instead, report them privately by emailing **james@think.dev**. Include:

- A description of the vulnerability
- Steps to reproduce it
- The version of `taskatlas` affected

You can expect an acknowledgement within 48 hours and a resolution or status update within 7 days.

## Scope

`taskatlas` is a zero-dependency, pure-Python library. It:

- Makes no network requests
- Reads and writes only local files (when `Atlas.save()` / `Atlas.load()` are called)
- Has no authentication, credentials, or secrets handling

The attack surface is limited to untrusted data passed into the public API or loaded via `Atlas.load()` from an untrusted JSON file.
