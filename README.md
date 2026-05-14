
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


## Sign-in flow (no captcha gymnastics)

The first time you run the plugin it kicks off a PKCE OAuth flow inside
a captive sign-in window:

1. The script pops a small `WKWebView` window titled "Sign in to Tesla"
   pointed at Tesla's official SSO endpoint.
2. You sign in normally — captcha, MFA, passkey, whatever Tesla throws
   at you. It all happens inside the captive window like the Tesla iOS
   app.
3. Once Tesla redirects to `tesla://auth/callback?code=...`, the
   webview's navigation delegate intercepts the request before the OS
   can hand it to the Tesla app, captures the auth code, and the window
   closes itself.
4. The script exchanges the code for tokens at
   `https://auth.tesla.com/oauth2/v3/token` and stores `access_token` +
   `refresh_token` in the macOS Keychain under the service name
   `mytesla-xbar`.

If PyObjC's WebKit bindings aren't available, the script falls back to
opening the URL in your default browser and asking you to copy the
`tesla://auth/callback?...` URL out of the address bar. To stay on the
smooth path, install:

```bash
pip3 install --user pyobjc-framework-WebKit pyobjc-framework-Cocoa
```

(They're already in `requirements.txt`.)

> Tesla retired the legacy `https://auth.tesla.com/void/callback`
> redirect for the `ownerapi` client_id in April 2026 — only
> `tesla://auth/callback` is registered now, which is why we host the
> sign-in inside our own webview instead of routing the user through a
> regular browser tab.


## Settings menu

Everything that used to be a hard-coded constant at the top of the
source file now lives in a Settings submenu (and in the macOS Keychain).
From the menubar pick **Settings → ...** to:

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

This plugin currently uses Tesla's *Owner API* (the same endpoints the
mobile app uses). Tesla has been slowly deprecating it in favour of the
new *Fleet API* — when that finally happens, the auth flow above is
already PKCE so the migration should mostly be a matter of swapping the
client_id and base URL. Tokens are short-lived (8 hours) and refreshed
automatically on every menu render.


## Changelog

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
