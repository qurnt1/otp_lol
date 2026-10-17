# Release

Release candidates are built from tags matching `v*`. The workflow runs backend checks, frontend API/type/build checks, builds the Windows executable, signs and verifies the executable and installer, runs the packaged self-test, computes SHA-256, then creates a **draft** GitHub Release. Keep the release in draft until the required manual League/WebView2 smoke test below passes, then publish it in GitHub. The HTTP smoke test remains a source/integration check because the release binary is intentionally windowed and does not expose a console.

The release must contain these exact assets:

- `OTP-LOL-Setup.exe`
- `OTP-LOL-Setup.exe.sha256`

The installer contains the onedir application and creates the desktop and Start Menu shortcuts. The checksum file contains the SHA-256 digest followed by the installer filename. The application and the public website use the exact installer asset instead of guessing from a generic `.exe` upload.

The release workflow validates on `windows-latest`, runs the generated API type check only after Python dependencies are installed, executes the Playwright suite on Windows, runs the packaged `--self-test --allow-missing-webview2`, and builds the installer with the version read from `src/config/constants.py`. The `Package Windows smoke` workflow performs the frontend build, PyInstaller onedir build, and packaged self-test on pull requests and important branch pushes without publishing a release. The installer and the real release smoke test remain responsible for validating the WebView2 machine prerequisite.

Before tagging:

1. Update the application version in the project constants.
2. Run the local backend, frontend, audit, and self-test commands from [`development.md`](development.md).
3. Confirm the tag version matches the application version.
4. Create and push the `vX.Y` tag.

The release workflow does not publish the draft automatically. After the smoke test, publish the draft manually. Older or schema-less settings files are intentionally replaced by defaults without migration or a `.bak`; include that behavior in the upgrade check before distribution.

The workflow creates the draft GitHub Release for each pushed tag. After the required smoke test passes, a maintainer publishes the draft manually. The workflow is intentionally not triggered by ordinary branch pushes.

Tagged releases require these GitHub Actions secrets:

- `OTP_LOL_SIGNING_CERT_BASE64`: base64-encoded Authenticode PFX certificate;
- `OTP_LOL_SIGNING_CERT_PASSWORD`: PFX password;
- `OTP_LOL_TIMESTAMP_URL`: RFC 3161 timestamp server URL.

The workflow signs `OTP LOL.exe` before building the installer, signs `OTP-LOL-Setup.exe` afterward, verifies both signatures, and only then generates the checksum. The certificate is written only to the ephemeral runner and removed at the end of the job.

The installer checks Microsoft Edge WebView2 Evergreen Runtime before installation. If it is missing, it opens the official download page and stops so the user can install the prerequisite before retrying.

Before broad public distribution, perform the real League/WebView2 smoke test below. Automated browser tests use a mocked local API and cannot replace this validation.

## Required League/WebView2 smoke test

Run this checklist on the exact signed installer built from the release tag:

1. Install as a standard user on a clean Windows account.
2. Confirm the desktop and Start Menu shortcuts launch the application.
3. Confirm the application reports an actionable WebView2 message when the runtime is absent, then installs and launches correctly after WebView2 is added.
4. Start with League closed and verify the offline/saved-account behavior.
5. Start League, sign in, and verify the LCU connection and detected account/region.
6. Complete a ready-check and champion select.
7. Verify preset fallback from priority 1 to 2/3, auto-ban, summoner spells, runes, and skin selection.
8. Verify the external statistics and live provider windows.
9. Verify tray behavior, `Alt+C`, and `Alt+P`.
10. Close and reopen OTP LOL, then close and reconnect League.
11. Verify settings, provider sessions, window geometry, and account state persist.
12. Exit through the tray and confirm there is no remaining OTP LOL process or lock file.
13. With a disposable profile containing an older or schema-less settings file, confirm the app resets it to current defaults and does not create a `.bak`.

Record the application version, release tag, pass/fail result, and redacted logs. Do not commit cookies, tokens, account identifiers, or screenshots containing personal data.
