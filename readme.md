<p align="center">
  <a href="https://github.com/qurnt1/otp_lol/releases"><img src="https://img.shields.io/badge/Windows-download-0078D6?logo=windows&logoColor=white" alt="Download for Windows"></a>
</p>

<h1 align="center">OTP LOL</h1>

<p align="center"><strong>Your League routine, ready before the match.</strong></p>

OTP LOL is a Windows companion for League of Legends that takes care of the repeatable client actions around queue, champion select, and the end of a game. Set your preferences once, then enable only the automations you want.

<p align="center">
  <a href="https://github.com/qurnt1/otp_lol/releases"><strong>Get OTP LOL for Windows</strong></a>
  &nbsp;|&nbsp;
  <a href="#see-it-in-action">See the app</a>
</p>

## Spend less time on the same setup

Every game brings familiar steps. OTP LOL keeps your choices together and can apply them when the League client is ready.

- **Get through queue faster.** Optionally accept ready checks and return to the lobby after a game.
- **Enter champion select with a plan.** Set pick priorities and a ban, then choose pre-picks and summoner spells for your presets.
- **Keep your loadout consistent.** Configure rune pages and fixed or random skins for each preset.
- **Make it yours.** Organize presets by role, use quick controls, and open your preferred player-stat pages.

OTP LOL works alongside the League client on your PC. It does not play the match or choose your strategy; it handles the client actions you configure.

## You stay in control

Start with every automation turned off. Choose your champions and loadouts, then enable actions one at a time. You can change your setup whenever you want from the dashboard and settings.

Your OTP LOL settings stay on your computer. There is no OTP LOL account, hosted profile, or advertising. The app may request public League metadata and update information. League-detected account details are excluded from settings exports. If you open a player-stat link, the selected third-party provider receives the profile URL.

## See it in action

<p align="center">
  <img src="./docs/images/dashboard-web.png" alt="OTP LOL dashboard" width="48%">
  <img src="./docs/images/settings-web.png" alt="OTP LOL settings" width="48%">
</p>

## Get started

1. Download the Windows installer from the [GitHub releases page](https://github.com/qurnt1/otp_lol/releases).
2. Open the League client and start OTP LOL.
3. Set your pick priorities, ban, spells, runes, and skins.
4. Turn on the automations you want.

The first launch includes editable example presets. Automations remain off until you enable them.

## What you need

- A Windows PC with the League of Legends client installed on the same machine.
- The Microsoft Edge WebView2 Evergreen Runtime.

OTP LOL checks for WebView2 when it starts. If it is missing, install the Evergreen Runtime and reopen the app.

## Privacy and compatibility

OTP LOL runs locally and talks to the League client on your own PC. It does not need an OTP LOL login or cloud dashboard.

OTP LOL is an independent community project and is not affiliated with or endorsed by Riot Games. League of Legends and related marks are property of Riot Games.

## For contributors

The [development guide](./docs/development.md) covers running from source and the project checks. Product behavior and release details are in the [release notes](./track_updates.md); the [architecture](./docs/architecture.md) and [security model](./docs/security.md) are available for implementation details.
