# Release

Releases are created from tags matching `v*`. The workflow runs backend checks, frontend API/type/build checks, builds the Windows executable, runs the packaged self-test, computes SHA-256, then creates a GitHub Release. The HTTP smoke test remains a source/integration check because the release binary is intentionally windowed and does not expose a console.

The release must contain these exact assets:

- `OTP-LOL-Setup.exe`
- `OTP-LOL-Setup.exe.sha256`

The installer contains the onedir application and creates the desktop and Start Menu shortcuts. The checksum file contains the SHA-256 digest followed by the installer filename. The application and the public website use the exact installer asset instead of guessing from a generic `.exe` upload.

Before tagging:

1. Update the application version in the project constants.
2. Run the local backend, frontend, audit, and self-test commands from [`development.md`](development.md).
3. Confirm the tag version matches the application version.
4. Create and push the `vX.Y` tag.

The workflow owns GitHub Release publication. It is intentionally not triggered by ordinary branch pushes.
