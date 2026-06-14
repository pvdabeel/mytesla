
# MyTesla — macOS Menubar plugin

Displays information about your Tesla vehicle in the macOS menubar, and lets
you remotely control the car. Built as an [xbar](https://xbarapp.com)
plugin.

![Imgur](https://i.imgur.com/5xMhwXM.jpg)


| Browse Vehicle options | Browse Vehicle images | Control charging |
| --- | --- | --- |
| ![Imgur](https://i.imgur.com/EJ6sT7E.jpg) | ![Imgur](https://i.imgur.com/o0wx7nD.jpg) | ![Imgur](https://i.imgur.com/5xMhwXM.jpg) |

| Control Airco | Control Media | Control Navigation |
| --- | --- | --- |
| ![Imgur](https://i.imgur.com/i1tRRsL.jpg) | ![Imgur](https://i.imgur.com/R36v4f9.jpg) | ![Imgur](https://i.imgur.com/ciLkZu8.jpg) |


Want a Tesla with free supercharging credits? Use my [referral code](http://ts.la/pieter9690).


## Requirements

* macOS (Big Sur or later — the menu bar icons assume modern AppKit).
* [xbar](https://github.com/matryer/xbar/releases/latest) 2.1.7-beta or newer.
* Python 3.9+.
* A Tesla account.
* Your own Tesla **Fleet API** application (see below). Tesla retired the
  legacy Owner API in 2026, so a developer app is now mandatory.

## Installation

1. Install xbar from [the releases page](https://github.com/matryer/xbar/releases/latest)
   and launch it once so it creates `~/Library/Application Support/xbar/plugins/`.
2. Install the Python dependencies:

   ```bash
   pip3 install --user -r requirements.txt
   ```
3. Copy `mytesla.15m.py` and the `library/` directory into your xbar
   plugins folder, and make the script executable:

   ```bash
   cp -R mytesla.15m.py library \
     "$HOME/Library/Application Support/xbar/plugins/"
   chmod +x "$HOME/Library/Application Support/xbar/plugins/mytesla.15m.py"
   ```
4. Open xbar and let it pick up the new plugin. The menubar entry will
   show "Click here to set up MyTesla" — clicking it walks you through
   the sign-in flow described below.


## Fleet API setup (one-time)

Tesla retired the legacy Owner API in 2026 and migrated individual
accounts onto the official [Fleet API](https://developer.tesla.com/docs/fleet-api).
The Fleet API requires *your own* developer application, so there's a
one-time setup before you can sign in:

1. Go to [developer.tesla.com](https://developer.tesla.com) and create an
   application (the app name must **not** contain the word "Tesla").
2. Grant the scopes **`vehicle_device_data`**, **`vehicle_location`**,
   **`vehicle_cmds`** and **`vehicle_charging_cmds`** (the last two enable
   lock/unlock, climate, charging and other commands).
3. Set an **Allowed Redirect URI** (e.g. `https://<your-domain>/success`).
   It just needs to be a page that loads; the plugin captures the
   `?code=...` from it.
4. Host your application's public key on your partner domain and register
   the domain with Tesla (per Tesla's Fleet API docs).
5. In the menu bar, pick **Settings → Set up Tesla Fleet API credentials**
   and enter your `client_id`, `client_secret`, region (`eu`/`na`/`cn`)
   and the exact redirect URI from step 3. These are stored in the macOS
   Keychain under the service name `mytesla-xbar`.

> Fleet API usage is billed to your developer account (with a $10/month
> free credit). `vehicle_data` polling and wake-ups consume it, so keep an
> eye on the usage page on developer.tesla.com.


## Sign-in flow

Once the Fleet API credentials are configured, click **Login to tesla.com**
(or **Settings → Sign in again**) to run the OAuth flow inside a captive
sign-in window:

1. The script pops a small `WKWebView` window titled "Sign in to Tesla"
   pointed at Tesla's official SSO endpoint, using your `client_id` and
   the Fleet scopes.
2. You sign in normally — captcha, MFA, passkey, whatever Tesla throws
   at you. It all happens inside the captive window like the Tesla iOS
   app.
3. Once Tesla redirects to your `<redirect_uri>?code=...`, the webview's
   navigation delegate intercepts the request, captures the auth code,
   and the window closes itself.
4. The script exchanges the code for tokens (sending your `client_secret`
   and the regional `audience`) at the Fleet token endpoint
   `https://fleet-auth.prd.vn.cloud.tesla.com/oauth2/v3/token`, stores
   `access_token` + `refresh_token` in the Keychain, and confirms the
   account's regional API base via `GET /api/1/users/region`.

If PyObjC's WebKit bindings aren't available, the script falls back to
opening the URL in your default browser and asking you to copy the
redirect URL out of the address bar. To stay on the smooth path, install:

```bash
pip3 install --user pyobjc-framework-WebKit pyobjc-framework-Cocoa
```

(They're already in `requirements.txt`.)


## Settings menu

Everything that used to be a hard-coded constant at the top of the
source file now lives in a Settings submenu (and in the macOS Keychain).
From the menubar pick **Settings → ...** to:

* **Set up Tesla Fleet API credentials.** Enter your developer-app
  `client_id`, `client_secret`, region and redirect URI (see the Fleet
  API setup section above). Required before you can sign in.
* **Set Google API keys.** Maps and reverse-geocoding are optional;
  paste your own [Static Maps](https://developers.google.com/maps/documentation/maps-static)
  and [Geocoding](https://developers.google.com/maps/documentation/geocoding)
  keys and they'll be stored securely in Keychain.
* **Override option codes.** If Tesla's API returns the wrong option
  list for your VIN (a common problem on older cars), enter the correct
  comma-separated codes here. Stored per-vehicle in Keychain.
* **Refresh option codes from the internet.** Pulls the latest known
  Tesla option codes (parsed from the public
  [timdorr/tesla-api](https://tesla-api.timdorr.com) reference) and
  caches them under `~/.state/mytesla/`.
* **Toggle features.** Location tracking, battery percentage in the
  menubar, white logo, high-resolution composer image pre-cache.
* **Sign out.** Wipes tokens from Keychain so you can sign in to a
  different Tesla account.


## Notes on the underlying Tesla API

This plugin uses Tesla's official *Fleet API*. Tesla retired the legacy
*Owner API* (`owner-api.teslamotors.com`) in 2026 — it now returns
`403 forbidden` for migrated accounts — so a Fleet API developer app is
required (see the Fleet API setup section). Data reads (battery, location,
climate, charge, sentry status) work with a bearer token. **Vehicle
commands** (lock/unlock, climate, charging, trunk, navigation, etc.) need
the `vehicle_cmds` / `vehicle_charging_cmds` scopes.

Modern vehicles (most cars built 2021+) additionally require
cryptographically *signed* requests via the Tesla Vehicle Command Protocol,
which means running Tesla's `tesla-http-proxy` and pairing a virtual key to
the car. Older Intel-based Model S/X (which report
`vehicle_command_protocol_required: false` on the `fleet_status` endpoint)
accept **unsigned** REST commands directly, so this build sends them
straight to the Fleet API with no proxy or key pairing. If your car reports
that it *does* require the protocol, commands will be rejected with a 403
until proxy-based signing is added.

Tokens are short-lived and refreshed automatically on every menu render.


## Changelog

**2026.06:**
- [X] Migrated from the retired Owner API to the official Tesla Fleet API (data/display).
- [X] New Fleet API credential setup wizard (`Settings → Set up Tesla Fleet API credentials`): client_id, client_secret, region and redirect URI, all stored in the Keychain.
- [X] OAuth now uses your own developer app + `client_secret` + regional `audience`; regional API base auto-detected via `users/region`.
- [X] Fixed the endless "Login to tesla" loop: the menu now distinguishes "not configured", "not signed in" and a valid-token API rejection (401/403) and shows an honest status instead of looping.
- [X] Vehicle commands over the Fleet API: added the `vehicle_cmds` / `vehicle_charging_cmds` scopes, command bodies now sent as JSON, and friendly success/failure reporting. Works unsigned on pre-2021 Intel Model S/X (`vehicle_command_protocol_required: false`); signed-command support via `tesla-http-proxy` for newer cars is still pending.
- [X] `remote_start_drive` updated for Fleet API (no longer prompts for a password — enables keyless driving).

**2026.05:**
- [X] Embedded `WKWebView` sign-in window (Tesla-iOS-app-style). No more captcha screen, no more copy/paste, no more "redirect_uri not registered" errors.
- [X] Updated `redirect_uri` to the new `tesla://auth/callback` that Tesla's `ownerapi` client requires as of April 2026.
- [X] All credentials, Google API keys and toggles moved to the macOS Keychain.
- [X] New Settings submenu for keys, option-code overrides, feature toggles and sign-out.
- [X] Tesla option codes split out of the source into a JSON file that can be refreshed from the internet on demand.
- [X] HTTP timeouts + retry adapter on every Tesla, Google and composer call (xbar can no longer hang on a slow Tesla edge).
- [X] Bug fixes: rear-driver window control, charging-amperage menu, route-arrival typo, location-cache growth cap.
- [X] LICENSE, requirements.txt, .gitignore added.

**2023.12.03:**
- [X] Testing new Tesla Fleet API (location tracking).

**2022.11.01:**
- [X] Ready for Python 3 and macOS Ventura.
- [X] Improved seat heating support: 7 seats.
- [X] Improved steering heating support.
- [X] Displays current Station / Song / Title.
- [X] Displays current volume.
- [X] Updated composer images.

**2022.05.21:**
- [X] Automatically refreshes Tesla's 8-hour API tokens.

**2021.11.02:**
- [X] Support for xbar, deprecating bitbar.
- [X] Provide option to paste an `access_token` directly during init.

**2021.08.04:**
- [X] Support for auth.tesla.com captcha.
- [X] Support for showing battery in menu bar.
- [X] Support for white logo in menu bar on Big Sur.

**2020.02.06:**
- [X] Offline mode: shows last known state while the car is asleep, with a manual wake-up option.
- [X] Improved location tracking performance.
- [X] Ability to override option codes per vehicle.

**2020.02.04:**
- [X] Support for auth.tesla.com including MFA.
- [X] Code cleanup.

**2019.10.02:**
- [X] Display window status.
- [X] Show software update progress and version info.

**2019.09.30:**
- [X] Larger Google map.

**2019.09.29:**
- [X] V10 firmware support.
- [X] Window control.
- [X] Trigger Homelink.
- [X] Share to vehicle.
- [X] Maximum window defrost.

**2019.07.01:**
- [X] Show service appointments.
- [X] Catalina beta support.

**2019.04.13:**
- [X] Dog Mode.
- [X] Sentry Mode.
- [X] More information when vehicle is in service.

**2019.03.06:**
- [X] Compose car image based on option list.

**2019.02.05:**
- [X] Continuous location tracking to a TinyDB (can be disabled).
- [X] Google maps are cached (~25% performance improvement).

**2019.01.03:**
- [X] Remote control seat heaters.
- [X] List and navigate to nearby superchargers or destination chargers.

**2018.12.16:**
- [X] Set navigation to nearby charging site (firmware 2018.48 or higher).
- [X] Display vehicle option codes.

**2018.12.08:**
- [X] Remotely set your navigation.

**2018.12.01:**
- [X] Schedule software update.
- [X] Toggle media on and off.
- [X] Next / previous track.
- [X] Volume up / down.

**2018.07.30:**
- [X] Dark-mode-aware Google maps.
- [X] Uses CoreLocation to put your own GPS coordinates on the map alongside the car.

**2018.04.05:**
- [X] Shows vehicle info (VIN, color, wheels, type, model, Ludicrous).
- [X] "Uncorked" indicator.
- [X] Copy VIN to clipboard.
- [X] Hold ALT to run any menu command in Terminal.

**2018.03.22:**
- [X] Open / close trunks and charge port.
- [X] Performance optimizations.
- [X] Live Google Maps location (toggle between map and satellite).

**2018.02.21:** Tesla firmware 2018.4 / APIv3.
- [X] Battery loss percentage due to cold.
- [X] Rear and front window defroster status.
- [X] Battery heating status.

**2017.11.01:** (beta) Schedule charging / heating via Calendar or Reminders.

**2017.10.23:** Added color support.

**2017.10.22:** Added support for remote:
- [X] Keyless driving.
- [X] Charge level / charging control.
- [X] Lock and unlock.
- [X] Climate control.
- [X] Sunroof.
- [X] Flash lights and honk horn.


## Credits

* Greg Glockner — original [teslajson](https://github.com/gglockner/teslajson) Python client.
* Tim Dorr — [tesla-api](https://tesla-api.timdorr.com) reference docs and [optioncodes.md](https://github.com/timdorr/tesla-api/blob/master/optioncodes.md), used as the source of truth for the bundled `library/tesla_option_codes.json`.
* Adrian Kumpf — [tesla_auth](https://github.com/adriankumpf/tesla_auth) inspired the PKCE-in-the-browser sign-in approach.


## License

GPL v3 — see [LICENSE](./LICENSE).
