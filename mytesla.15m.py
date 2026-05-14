#!/usr/bin/env PYTHONIOENCODING=UTF-8 /opt/local/bin/python3 
#/ -*- coding: utf-8 -*-
#
# <xbar.title>MyTesla</xbar.title>
# <xbar.version>Tesla API v48</xbar.version>
# <xbar.author>pvdabeel@mac.com</xbar.author>
# <xbar.author.github>pvdabeel</xbar.author.github>
# <xbar.desc>Control your Tesla vehicle from the MacOS menubar</xbar.desc>
# <xbar.dependencies>python</xbar.dependencies>
#
# Licence: GPL v3

# Installation instructions: 
# -------------------------- 
# Execute in terminal.app before running : 
#    sudo easy_install keyring
#
# Ensure you have xbar installed https://github.com/matryer/xbar/releases/latest
# Copy this file to your xbar plugins folder and chmod +x the file from your terminal in that folder
# Run xbar

_DEBUG_ = False

# Keychain service used for everything (tokens, Google API keys, settings,
# per-vehicle option-code overrides). Picking a single namespace makes it easy
# to wipe state with `security delete-generic-password -s mytesla-xbar`.
KEYRING_SERVICE = "mytesla-xbar"

# Source-of-truth URL for the bundled Tesla option-code dictionary. The
# "Settings -> Update Tesla option codes" menu item downloads a fresh copy
# from here and writes it to ~/.state/mytesla/tesla_option_codes.json. The
# raw markdown table is parsed locally; no third-party API is involved.
OPTION_CODES_REMOTE_URL = (
    "https://raw.githubusercontent.com/timdorr/tesla-api/master/docs/"
    "vehicle/optioncodes.md"
)

# Hard-coded layout / picture defaults. These don't need to live in the
# keychain because they're not secrets and changing them is rare; users who
# really want different views can edit this file. Everything else (keys,
# overrides, toggles) is now configurable via the in-app Settings submenu.
_SHOW_CAR_PICTURES_     = ['STUD_SIDE_V2', 'STUD_3QTR', 'STUD_REAR',
                           'STUD_WHEEL_V2', 'STUD_SEAT_V2', 'INTERIOR']
_CAR_DEFAULT_PICTURE_   = 'STUD_SIDE_V2'
_CAR_DEFAULT_PICTURE_2_ = 'STUD_WHEEL_V2'


import base64
import calendar
import datetime
import getpass                                  
import json
import keyring                                  
import math
import os
import random
import re
import requests
import string
import sys
import time
import platform
import urllib
import urllib.parse

from googlemaps     import Client as googleclient
from hashlib        import sha256
from tinydb         import TinyDB, Query
from urllib.parse   import parse_qs
from datetime       import date
from datetime       import datetime

# Location where to store state files
home         = os.path.expanduser("~")
state_dir    = home+'/.state/mytesla'

if not os.path.exists(state_dir):
    os.makedirs(state_dir)

# The full path to this file                                                    
                                                                                
cmd_path = os.path.realpath(__file__) 

# Location tracking database
locationdb = TinyDB(state_dir+'/mytesla-locations.json')
geolocdb   = TinyDB(state_dir+'/mytesla-geoloc.json')

# Cap the on-disk locations history so it doesn't grow without bound.
# At one insert per ~15-minute menu refresh, 5000 rows is roughly 52 days
# of continuous tracking — plenty for the "find my car" use-case while
# keeping the JSON file small enough to load quickly.
LOCATIONDB_MAX_ROWS = 5000
GEOLOCDB_MAX_ROWS   = 5000


def _tinydb_clear(db):
    """Empty a TinyDB instance, regardless of v3 (``purge``) vs v4 (``truncate``)."""
    fn = getattr(db, "truncate", None) or getattr(db, "purge", None)
    if fn is None:
        return
    try:
        fn()
    except Exception:
        pass


def _tinydb_trim(db, max_rows):
    """Drop the oldest rows of ``db`` so it never exceeds ``max_rows``.

    Best-effort: failures here are non-fatal. The DB grows ~1 row per
    refresh, so this only does work when the user has been running for
    weeks.
    """
    try:
        docs = db.all()
    except Exception:
        return
    excess = len(docs) - max_rows
    if excess <= 0:
        return
    try:
        oldest_ids = sorted(d.doc_id for d in docs)[:excess]
        db.remove(doc_ids=oldest_ids)
    except Exception:
        try:
            keep = docs[-max_rows:]
            _tinydb_clear(db)
            db.insert_multiple(keep)
        except Exception:
            pass


# --------------------------
# Keyring + settings helpers
# --------------------------
#
# Anything that used to live in a top-level constant (Google API keys, the
# per-vehicle option-code overrides, the various toggle flags) now lives in
# the macOS Keychain under the `mytesla-xbar` service. The accessors below
# provide a single, defensive interface so the menu code never has to deal
# with `keyring` raising or returning ``None``.

def kr_get(key, default=None):
    try:
        return keyring.get_password(KEYRING_SERVICE, key) or default
    except Exception:
        return default


def kr_set(key, value):
    if value is None:
        return
    try:
        keyring.set_password(KEYRING_SERVICE, key, str(value))
    except Exception:
        pass


def kr_delete(key):
    try:
        keyring.delete_password(KEYRING_SERVICE, key)
    except Exception:
        pass


def kr_get_bool(key, default):
    """Return a stored bool flag. Defaults flow through unchanged."""
    raw = kr_get(key, None)
    if raw is None:
        return default
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


# Settings accessors. Defaults match the behavior of the old hard-coded
# constants. These are the single source of truth — every menu item that
# used to read `_LOCATION_TRACKING_` / `_BATTERY_MENUBAR_` / etc. now reads
# its value through one of these.

def setting_location_tracking():
    return kr_get_bool("setting_location_tracking", True)


def setting_battery_menubar():
    return kr_get_bool("setting_battery_menubar", False)


def setting_white_logo():
    return kr_get_bool("setting_white_logo", True)


def setting_composer_cache_high():
    return kr_get_bool("setting_composer_cache_high", True)


def setting_map_size():
    return kr_get("setting_map_size", "800x600")


def get_google_static_key():
    """Google Static Maps API key (used for the menu-bar map images)."""
    return kr_get("google_static_key")


def get_google_geocode_key():
    """Google Geocoding API key (used for reverse-geocoding the car location)."""
    return kr_get("google_geocode_key")


def get_override_option_codes():
    """Return ``{vehicle_id: "CODE1,CODE2,..."}`` from keyring as a dict.

    Stored as a single JSON blob under the ``override_option_codes`` key, so
    the user can manage all overrides in one place via the Settings menu.
    """
    raw = kr_get("override_option_codes")
    if not raw:
        return {}
    try:
        decoded = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    if not isinstance(decoded, dict):
        return {}
    out = {}
    for k, v in decoded.items():
        try:
            out[int(k)] = str(v)
        except (TypeError, ValueError):
            continue
    return out


def set_override_option_codes(mapping):
    """Persist a ``{vehicle_id: "CSV"}`` mapping to keyring."""
    serializable = {str(int(k)): str(v) for k, v in mapping.items()}
    kr_set("override_option_codes", json.dumps(serializable))


# Tesla option codes
#
# The full code -> human-readable label mapping is bundled as a JSON file
# alongside this script (`library/tesla_option_codes.json`). Users can refresh
# it from the latest community-maintained source at any time via the
# in-app "Settings -> Update Tesla option codes" menu, which writes the new
# JSON to ~/.state/mytesla/tesla_option_codes.json. The loader below prefers
# the user's state file (if present), then falls back to the bundle.

_BUNDLED_OPTION_CODES_PATH = os.path.join(
    os.path.dirname(os.path.realpath(__file__)),
    "library",
    "tesla_option_codes.json",
)
_USER_OPTION_CODES_PATH = state_dir + "/tesla_option_codes.json"


def _load_option_codes():
    """Return {code: label}, picking the freshest source available."""
    for path in (_USER_OPTION_CODES_PATH, _BUNDLED_OPTION_CODES_PATH):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                return {str(k): str(v) for k, v in data.items()}
        except (OSError, ValueError):
            continue
    return {}


tesla_option_codes = _load_option_codes()


# Nice ANSI colors
CEND    = '\33[0m'
CRED    = '\33[31m'
CGREEN  = '\33[32m'
CYELLOW = '\33[33m'
CBLUE   = '\33[36m'

# Support for OS X Dark Mode
DARK_MODE=True if os.getenv('XBARDarkMode','false') == 'true' else False


# --------------------------
# TeslaAuthenticator
# --------------------------

class TeslaAuthenticator(object):
    """PKCE OAuth2 client for Tesla's owner API, with an embedded sign-in window.

    Tesla's owner-API SSO accepts only one ``redirect_uri`` for the
    public ``ownerapi`` client: ``tesla://auth/callback`` (a custom URL
    scheme that the Tesla iOS app normally claims). Driving this from a
    regular desktop browser is awkward because the OS will try to hand
    the ``tesla://`` URL to the iOS app the moment the browser navigates
    to it.

    The fix is to pop a captive sign-in window using ``WKWebView`` (via
    PyObjC) and intercept the navigation to ``tesla://auth/callback?...``
    inside the webview itself, before the OS protocol handler runs. This
    is exactly what the Tesla iOS app does and what ``tesla_auth`` does
    on desktop. Captcha / MFA / passkey prompts all work because we're
    using a real ``WKWebView``.

    The flow:

    1. Generate a PKCE verifier/challenge pair and the OAuth ``authorize``
       URL.
    2. Open that URL in an embedded ``WKWebView`` window.
    3. When the webview tries to navigate to ``tesla://auth/callback?code=...``,
       intercept the request, capture ``code`` + ``state``, close the
       window.
    4. Exchange the code for tokens at ``/oauth2/v3/token`` using the
       PKCE verifier.
    5. Store ``access_token`` + ``refresh_token`` in the macOS Keychain.

    If PyObjC's WebKit bindings aren't available we fall back to a manual
    flow that opens the browser and asks the user to copy the
    ``tesla://...`` URL out of the address bar.
    """

    AUTH_URL     = "https://auth.tesla.com/oauth2/v3/authorize"
    TOKEN_URL    = "https://auth.tesla.com/oauth2/v3/token"
    # NB: as of April 2026 this is the *only* redirect_uri registered
    # for client_id=ownerapi. The legacy https://auth.tesla.com/void/callback
    # now returns "redirect_uri not registered". See
    # https://github.com/teslamate-org/teslamate/issues/5296 and the fix
    # in https://github.com/GewoonJaap/tesla_auth.
    REDIRECT_URI = "tesla://auth/callback"

    # Window size for the embedded sign-in webview. Big enough that the
    # Tesla SSO + captcha widgets don't overflow on a Retina display.
    _WEBVIEW_WIDTH      = 520
    _WEBVIEW_HEIGHT     = 720
    _CAPTURE_TIMEOUT_S  = 600   # 10 minutes — generous for slow MFA flows

    headers = {
        "Accept": "application/json",
        # Tesla's WAF flags requests that look browser-y; keep it neutral.
        "User-Agent": "mytesla-xbar/1.0",
    }

    credentials = {}

    def __init__(self):
        return None

    # -- prompts -----------------------------------------------------------

    def dialog_redirect_url(self):
        print("")
        print(CRED + "Paste the full URL from your browser's address bar"
              + CEND)
        print("(it begins with " + self.REDIRECT_URI + "?code=...):")
        return str_input().strip()

    def dialog_access_token(self):
        print(CRED + 'Enter Tesla access token:' + CEND)
        return str_input().strip()

    def dialog_refresh_token(self):
        print(CRED + 'Enter Tesla refresh token:' + CEND)
        return str_input().strip()

    # -- PKCE helpers ------------------------------------------------------

    @staticmethod
    def _pkce_pair():
        """Return ``(verifier_str, challenge_str)`` per RFC 7636 (S256)."""
        verifier = base64.urlsafe_b64encode(os.urandom(64)).rstrip(b"=").decode("ascii")
        digest = sha256(verifier.encode("ascii")).digest()
        challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        return verifier, challenge

    # -- embedded sign-in window (WKWebView) -------------------------------

    def _capture_redirect_via_webview(self, auth_url):
        """Open a captive ``WKWebView`` window and capture ``tesla://auth/callback``.

        Returns the captured callback URL string, or ``None`` if PyObjC's
        WebKit bindings aren't installed (in which case the caller falls
        back to the manual paste flow).
        """
        try:
            import objc
            import AppKit
            import WebKit
            from Foundation import NSObject, NSURL, NSURLRequest
        except ImportError:
            return None

        REDIRECT_URI = self.REDIRECT_URI
        captured = {"url": None}

        # `WKNavigationDelegate` callback. We need to vet *every* navigation
        # attempt: if the target is `tesla://auth/callback?...`, swallow it,
        # stash it, and tear down the window. Anything else we let proceed
        # so the user can complete sign-in.
        class _NavDelegate(NSObject):
            def webView_decidePolicyForNavigationAction_decisionHandler_(
                self, webView, navigationAction, decisionHandler,
            ):
                request = navigationAction.request()
                url = request.URL().absoluteString() if request.URL() else ""
                if url and url.startswith(REDIRECT_URI):
                    captured["url"] = str(url)
                    # WKNavigationActionPolicyCancel = 0
                    decisionHandler(0)
                    AppKit.NSApp.stop_(self)
                else:
                    # WKNavigationActionPolicyAllow = 1
                    decisionHandler(1)

        # Make sure we have an NSApplication. xbar runs us as a CLI subprocess
        # so we have to bootstrap one ourselves.
        app = AppKit.NSApplication.sharedApplication()
        app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyRegular)

        rect = AppKit.NSMakeRect(0, 0, self._WEBVIEW_WIDTH, self._WEBVIEW_HEIGHT)
        style = (
            AppKit.NSWindowStyleMaskTitled
            | AppKit.NSWindowStyleMaskClosable
            | AppKit.NSWindowStyleMaskResizable
        )
        window = AppKit.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            rect, style, AppKit.NSBackingStoreBuffered, False,
        )
        window.setTitle_("Sign in to Tesla")
        window.center()

        config = WebKit.WKWebViewConfiguration.alloc().init()
        webview = WebKit.WKWebView.alloc().initWithFrame_configuration_(rect, config)
        webview.setAutoresizingMask_(
            AppKit.NSViewWidthSizable | AppKit.NSViewHeightSizable
        )

        delegate = _NavDelegate.alloc().init()
        webview.setNavigationDelegate_(delegate)
        # The local `delegate` reference keeps the Objective-C object
        # alive across the run loop. (PyObjC native objects don't accept
        # arbitrary Python attribute assignment.)

        window.contentView().addSubview_(webview)
        window.makeKeyAndOrderFront_(None)
        app.activateIgnoringOtherApps_(True)

        request = NSURLRequest.requestWithURL_(NSURL.URLWithString_(auth_url))
        webview.loadRequest_(request)

        # Watchdog: stop the run loop after CAPTURE_TIMEOUT_S so we never
        # hang the user's terminal forever if they walk away from the
        # window without signing in.
        try:
            from Foundation import NSTimer
            def _watchdog(_t):
                if captured["url"] is None:
                    AppKit.NSApp.stop_(None)
            timer = NSTimer.scheduledTimerWithTimeInterval_repeats_block_(
                self._CAPTURE_TIMEOUT_S, False, _watchdog,
            )
        except Exception:
            timer = None

        # Run the modal-ish loop until the delegate (or watchdog) calls
        # NSApp.stop_(). The user closing the window will also drop us out
        # naturally because the next event picks up the stop flag.
        try:
            app.run()
        except KeyboardInterrupt:
            pass
        finally:
            try:
                if timer is not None:
                    timer.invalidate()
            except Exception:
                pass
            try:
                window.close()
            except Exception:
                pass

        return captured["url"]

    # -- main login flow ---------------------------------------------------

    def perform_login(self):
        """Run the PKCE flow in an embedded WebView and persist new credentials."""
        verifier, challenge = self._pkce_pair()
        state = random_string(12)

        params = {
            "client_id"             : "ownerapi",
            "code_challenge"        : challenge,
            "code_challenge_method" : "S256",
            "redirect_uri"          : self.REDIRECT_URI,
            "response_type"         : "code",
            "scope"                 : "openid email offline_access",
            "state"                 : state,
        }
        auth_url = self.AUTH_URL + "?" + urllib.parse.urlencode(params)

        # Preferred path: pop a captive WKWebView, intercept the
        # tesla://auth/callback navigation in-process. Zero copy/paste.
        print("")
        print("Opening Tesla sign-in window...")
        print("Sign in normally — captcha, MFA and passkey prompts all work.")
        print("This window will close automatically once you're signed in.")
        print("")
        redirect_url = self._capture_redirect_via_webview(auth_url)

        # Fallback: PyObjC isn't installed, or the user closed the window
        # before signing in. Open the URL in their browser and ask them to
        # copy the tesla:// URL out of the address bar.
        if not redirect_url:
            print("")
            print(CRED + "Embedded sign-in window unavailable." + CEND)
            print("")
            print("Falling back to browser sign-in. Steps:")
            print("")
            print("  1. Tesla's sign-in page will open in your default browser.")
            print("  2. Sign in normally.")
            print("  3. Tesla will redirect to a 'tesla://auth/callback?code=...'")
            print("     URL. Your browser will say it can't open the link —")
            print("     that's fine. Copy the full URL from the address bar")
            print("     (it begins with " + self.REDIRECT_URI + ").")
            print("  4. Paste that URL back here.")
            print("")
            print("Tip: install PyObjC's WebKit bindings to skip this dance:")
            print("     pip3 install --user pyobjc-framework-WebKit")
            print("")
            print("If the browser doesn't open, here's the URL to use:")
            print("")
            print("  " + auth_url)
            print("")
            try:
                import webbrowser
                webbrowser.open(auth_url, new=2)
            except Exception:
                pass

            for _attempt in range(3):
                pasted = self.dialog_redirect_url()
                if pasted and pasted.startswith(self.REDIRECT_URI):
                    redirect_url = pasted
                    break
                if pasted:
                    print(CRED + "That doesn't look like a "
                          + self.REDIRECT_URI + " URL. Try again." + CEND)
            if not redirect_url:
                print(CRED + "Giving up. Run sign-in again to retry." + CEND)
                return

        # Parse and validate the redirect URL.
        try:
            parsed = urllib.parse.urlparse(redirect_url)
            qs = urllib.parse.parse_qs(parsed.query)
        except Exception:
            qs = {}
        code = qs.get("code", [None])[0]
        returned_state = qs.get("state", [None])[0]
        if not code:
            print(CRED + "No 'code' parameter in the redirect URL. Aborting."
                  + CEND)
            return
        if returned_state and returned_state != state:
            print(CRED + "OAuth state mismatch — possible interception. "
                         "Aborting." + CEND)
            return

        # Exchange the authorization code for tokens.
        payload = {
            "grant_type"    : "authorization_code",
            "client_id"     : "ownerapi",
            "code"          : code,
            "code_verifier" : verifier,
            "redirect_uri"  : self.REDIRECT_URI,
        }
        try:
            response = requests.post(self.TOKEN_URL, json=payload,
                                     headers=self.headers, timeout=15)
        except requests.RequestException as exc:
            print(CRED + f"Token exchange failed: {exc}" + CEND)
            return

        if response.status_code != 200:
            print(CRED + f"Token exchange returned {response.status_code}."
                         f" Response: {response.text[:300]}" + CEND)
            print("")
            print("If your browser sign-in completed but this step keeps")
            print("failing, you can paste tokens by hand — for example from")
            print("https://github.com/adriankumpf/tesla_auth.")
            access_token = self.dialog_access_token()
            refresh_token = self.dialog_refresh_token()
            if access_token and refresh_token:
                self.override_credentials(access_token, refresh_token)
                print(CGREEN + "Tokens saved to macOS Keychain." + CEND)
            return

        try:
            self.credentials = response.json()
        except ValueError:
            print(CRED + "Token endpoint returned non-JSON. Aborting." + CEND)
            return

        if not self.credentials.get("access_token"):
            print(CRED + "No access_token in response. Aborting." + CEND)
            return

        self.save_credentials()
        print("")
        print(CGREEN + "Login successful — tokens stored in macOS Keychain."
              + CEND)
        print("You can close this Terminal window. The MyTesla menu bar will")
        print("refresh on its own.")

    # -- token persistence -------------------------------------------------

    def load_credentials(self):
        self.credentials = {
            "access_token"  : kr_get("access_token"),
            "refresh_token" : kr_get("refresh_token"),
            "token_type"    : "bearer",
        }

    def save_credentials(self):
        if self.credentials.get("access_token"):
            kr_set("access_token", self.credentials["access_token"])
        if self.credentials.get("refresh_token"):
            kr_set("refresh_token", self.credentials["refresh_token"])

    def override_credentials(self, access_token, refresh_token):
        kr_set("access_token", access_token)
        kr_set("refresh_token", refresh_token)
        self.credentials = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }

    def refresh_credentials(self):
        refresh_token = (self.credentials or {}).get("refresh_token")
        if not refresh_token:
            return
        payload = {
            "grant_type"    : "refresh_token",
            "client_id"     : "ownerapi",
            "refresh_token" : refresh_token,
            "scope"         : "openid email offline_access",
        }
        try:
            response = requests.post(self.TOKEN_URL, json=payload,
                                     headers=self.headers, timeout=15)
            data = response.json()
        except (requests.RequestException, ValueError):
            return
        if response.status_code != 200 or not data.get("access_token"):
            return
        # Tesla's refresh endpoint may or may not include a new refresh_token.
        # Preserve the old one if it didn't.
        data.setdefault("refresh_token", refresh_token)
        self.credentials = data
        self.save_credentials()



class TeslaConnection(object):
    """Thin wrapper around the Tesla owner API with timeouts + retries.

    Every menu refresh used to be one slow synchronous request. Worse, none
    of them had timeouts — so a stalled Tesla edge could pin the entire
    xbar plugin until the next refresh. This class adds:

        * a per-request timeout (so we never block the menu indefinitely),
        * a retry adapter for transient 5xx / 502 / 504 / 429 responses,
        * a single shared ``requests.Session`` for connection pooling.
    """

    BASE_URL = "https://owner-api.teslamotors.com/api/1/"
    REQUEST_TIMEOUT_S = 12

    def __init__(self, access_token):
        self.headers = {
            "Accept": "application/json",
            # Tesla's WAF blocks anything that looks too "browser-y", but it
            # also blocks bare User-Agents from `requests`. Pick something
            # neutral that identifies us.
            "User-Agent": "mytesla-xbar/1.0",
            "Authorization": "Bearer " + access_token,
        }
        self.session = self._build_session()

    @staticmethod
    def _build_session():
        s = requests.Session()
        try:
            try:
                from urllib3.util.retry import Retry
            except ImportError:
                from requests.packages.urllib3.util.retry import Retry  # type: ignore
            from requests.adapters import HTTPAdapter
            retry = Retry(
                total=3,
                connect=3,
                read=2,
                backoff_factor=0.5,
                status_forcelist=(429, 500, 502, 503, 504),
                allowed_methods=frozenset({"GET", "POST"}),
                raise_on_status=False,
            )
            adapter = HTTPAdapter(max_retries=retry, pool_connections=4,
                                  pool_maxsize=4)
            s.mount("https://", adapter)
            s.mount("http://", adapter)
        except Exception:
            # If urllib3's Retry isn't importable for some reason, we still
            # want a working session — just without retries.
            pass
        return s

    def vehicles(self):
        return [TeslaVehicle(v, self) for v in
                self.get('products?orders=true')['response']]

    def appointments(self):
        return self.get('users/service_scheduling_data')['response']

    def get(self, command):
        try:
            r = self.session.get(self.BASE_URL + command,
                                 headers=self.headers,
                                 timeout=self.REQUEST_TIMEOUT_S)
        except requests.RequestException:
            return {"response": None}
        try:
            return r.json()
        except ValueError:
            return {"response": None}

    def post(self, command, data=None):
        try:
            r = self.session.post(self.BASE_URL + command,
                                  data=data or {},
                                  headers=self.headers,
                                  timeout=self.REQUEST_TIMEOUT_S)
        except requests.RequestException:
            return {"response": None}
        try:
            return r.json()
        except ValueError:
            return {"response": None}



class TeslaVehicle(dict):
    """TeslaVehicle class, subclassed from dictionary.
    
    There are 3 primary methods: wake_up, data_request and command.
    data_request and command both require a name to specify the data
    or command, respectively. These names can be found in the
    Tesla JSON API."""

    def __init__(self, data, connection):
        """Initialize vehicle class
        
        Called automatically by the TeslaConnection class
        """
        super(TeslaVehicle, self).__init__(data)
        self.connection = connection
    

    def vehicle_data(self):
        """Get vehicle data"""
        if self.asleep() or self.offline(): 
            try:
                # Vehicle asleep or offline, getting info from local cache
                Q = Query()
                result = locationdb.search(Q.vehicle==self['vehicle_id'])[-1]['vehicle_data']
                return result['response']
            except:
                # Local cache failed, waking up vehicle
                self.post('wake_up')
                time.sleep(30)
                pass
        # Retrieve the vehicle data from Tesla API
        result = self.get('vehicle_data?endpoints=service_data%3Bcharge_state%3Bclimate_state%3Bclosures_state%3Bdrive_state%3Bgui_settings%3Blocation_data%3Bvehicle_config%3Bvehicle_state%3Bvehicle_data_combo')

        # Update local cache. When tracking is disabled we keep only the
        # most recent row (so the menu can still display "where the car
        # last was"); when enabled we append and periodically trim the
        # oldest rows so the JSON file doesn't grow unbounded.
        row = {
            'vehicle': self['vehicle_id'],
            'date': str(datetime.now()),
            'vehicle_data': result,
        }
        if setting_location_tracking():
            locationdb.insert(row)
            _tinydb_trim(locationdb, LOCATIONDB_MAX_ROWS)
        else:
            _tinydb_clear(locationdb)
            locationdb.insert(row)
        return result['response']
    

    def data_request(self, name):
        """Get vehicle data"""
        result = self.get('data_request/%s' % name)
        return result['response']
    

    def asleep(self):
        """Check if vehichle is asleep"""
        return self['state'] == "asleep"

    def offline(self):
        """Check if vehicle is offline"""
        return self['state'] == "offline"

    def wake_up(self):
        """Wake the vehicle"""
        return self.post('wake_up')
  

    def mobile_access(self):
        """Check if vehicle mobile access is enabled"""
        result = self.get('mobile_enabled')
        return result['response']


    def nearby_charging_sites(self):
        """Return list of nearby chargers"""
        try: # Firmware 2018.48 or higher needed
           return self.get('nearby_charging_sites')['response']
        except: 
           return []


    def model_short(self,model):
        """Return the short name for the vehicle model"""
        switcher = { 'modelx':'mx', 'models':'ms', 'model3':'m3'} 
        return switcher.get(model,model)

    def option_codes(self):
        """Return the comma-separated option-code string for this vehicle.

        Tesla's owner-API still returns generic placeholder codes since 2019,
        so users can store a per-vehicle override in the macOS Keychain via
        ``Settings -> Override option codes``. Lookup order:

            1. Keyring override keyed by ``vehicle_id`` (preferred).
            2. Whatever Tesla returned in the vehicle dict.
            3. Empty string.

        NB: this class subclasses ``dict`` *and* defines ``get()`` as an HTTP
        method, so we use ``dict.get(self, ...)`` to read the raw fields
        instead of accidentally hitting the network.
        """
        overrides = get_override_option_codes()
        override = overrides.get(dict.get(self, 'vehicle_id'))
        if override:
            return override
        codes = dict.get(self, 'option_codes')
        if isinstance(codes, str) and codes:
            return codes
        return ""

    def recent_alerts(self):
        """Return list of recent alerts"""
        return self.connection.get('vehicles/%i/recent_alerts' % self['id'])['response']

    def service_data(self):
        """Return service data"""
        return self.connection.get('vehicles/%i/service_data' % self['id'])['response']
    
    def release_notes(self):
        """Return release notes"""
        return self.connection.get('vehicles/%i/release_notes' % self['id'])['response']
    
    def command(self, name, data={}):
        """Run the command for the vehicle"""
        return self.post('command/%s' % name, data)

    def get(self, command):
        """Utility command to get data from API"""
        return self.connection.get('vehicles/%i/%s' % (self['id'], command))

    def post(self, command, data={}):
        """Utility command to post data to API"""
        return self.connection.post('vehicles/%i/%s' % (self['id'], command), data)

 
    def compose_url(self, model, size=2048, view=_CAR_DEFAULT_PICTURE_, background='1'):
        """Returns composed image url representing the car"""
        return 'https://static-assets.tesla.com/configurator/compositor?model='+self.model_short(model)+'&view='+view+'&size='+str(size)+'&options='+self.option_codes()+'&bkba_opt='+str(background)

    def compose_image(self, model, size=512, view=_CAR_DEFAULT_PICTURE_, background='1'):
        """Return the composed image (base64-encoded PNG) representing the car.

        On cache miss this fetches the PNG from Tesla's static configurator,
        with a strict timeout so the menu render never blocks on a slow
        edge. Returns ``None`` if Tesla served us anything other than a
        real PNG (auth issues, throttling, malformed options, ...).
        """
        cache_path = (state_dir + '/mytesla-composed-'
                      + str(self['vehicle_id']) + '-' + str(size) + '-'
                      + str(view) + '-' + str(background) + '.png')
        try:
            with open(cache_path, 'rb') as f:
                composed_img = f.read()
            if composed_img.startswith(b'\x89PNG\r\n\x1a\n'):
                return base64.b64encode(composed_img).decode('utf-8')
            return None
        except (OSError, IOError):
            pass

        my_headers = {
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Upgrade-Insecure-Requests': '1',
            'DNT': '1',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3.1 Safari/605.1.15',
        }
        composed_url = self.compose_url(model, size, view, background)
        try:
            composed_img = requests.get(composed_url, headers=my_headers,
                                        timeout=8)
        except requests.RequestException:
            return None
        if len(composed_img.content) > 309:
            try:
                with open(cache_path, 'wb') as f:
                    f.write(composed_img.content)
            except (OSError, IOError):
                pass
        if composed_img.content.startswith(b'\x89PNG\r\n\x1a\n'):
            return base64.b64encode(composed_img.content).decode('utf-8')
        return None


# Python 2/3 compat shim. The original code did `vars(__builtins__).get(...)`
# which broke when this file was imported (rather than executed) because
# ``__builtins__`` is a module object in that context, not a dict. We're
# Python-3-only now so just alias `input` directly.
str_input = input

# Check for png format
def is_png(filename):
    try:
        with open(filename, 'rb') as f:
            # PNG files start with these 8 bytes: 89 50 4E 47 0D 0A 1A 0A
            header = f.read(8)
            return header == b'\x89PNG\r\n\x1a\n'
    except (FileNotFoundError, IOError):
        return False


# Create a random string
def random_string(size):
    return ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(size))

# Base64 urlencode function
def base64urlencode(arg):
    stripped = arg.split("=")[0]
    filtered = stripped.replace("+", "-").replace("/", "_")
    return filtered

# Base64 urldecode function
def base64urldecode(arg):
    filtered = arg.replace("-", "+").replace("_", "/")
    padded = filtered + "=" * ((len(filtered) * -1) % 4)
    return padded

# Location Encoder function
def location_encoder(arg):
    return base64.b64encode(arg.encode('utf-8','ignore'))

# Location Decoder function
def location_decoder(arg):
    return base64.b64decode(arg[1:]).decode('utf-8')

# Convertor for temperature
def convert_temp(temp_unit,temp):
    if temp_unit == 'F':
        return (temp * 1.8) + 32
    else:
        return temp

# Convertor for distance
def convert_distance(distance_unit,distance):
    if distance_unit == 'km':
        return math.ceil(distance * 160.9344)/100
    else:
        return int(distance)

# Convertor for pressure
def convert_pressure(tirepressure,value):
    if tirepressure == 'Psi':
        return int(value * 14.5038)
    else:
        return value

# Pretty print door state
def door_state(dooropen):
    if bool(dooropen):
        return CRED + 'Open' + CEND + ' '
    else:
        return CGREEN + 'Closed' + CEND + ' '

# Pretty print window state
def window_state(windowopen):
    if (windowopen == 0):
        return CGREEN + 'Closed' + CEND + ' '
    elif (windowopen == 1):
        return CYELLOW + 'Vent' + CEND + ' '
    else: 
        return CRED + 'Open' + CEND + ' '

# Pretty print battery loss due to cold
def cold_state(percentage):
    if (percentage != 0):
        return CBLUE + '(-' + str(percentage) + '%)' + CEND
    else:
        return ''

# Pretty print tempereature setting
def color_setting(current,option,color,info_color):
    if (current == option): 
        return color 
    else: 
        return info_color

# Pretty print seat heater setting
def seat_state(temp):
    if (temp == 0):
        return 'Off'
    else:
        return 'On, level: ' + str(temp)

# Pretty print charge port state 
def port_state(portopen,engaged):
    if bool(portopen):
        if (engaged == 'Engaged'):
           return CYELLOW + 'In use' + CEND
        else:
           return CRED + 'Open' + CEND
    else:
        return CGREEN + 'Closed' + CEND
        
# Pretty print car lock state 
def lock_state(locked):
    if bool(locked):
        return CGREEN + 'Locked' + CEND
    else:
        return CRED + 'Unlocked' + CEND

# Pretty print sentry mode state 
def sentry_state(state):
    if bool(state):
        return CGREEN + '(Sentry On)'+ CEND
    else: 
        return CRED + '(Sentry Off)' + CEND


# ---- Pretty-printers for newly-surfaced API fields ---------------------

def shift_state_label(s):
    """Return ``Park``/``Reverse``/``Neutral``/``Drive`` or ``Parked`` for None.

    Tesla's API returns ``None`` for the shift state when the car is
    parked/asleep, the single-letter codes ``P/R/N/D`` while in motion.
    """
    return {
        'P': 'Park',
        'R': 'Reverse',
        'N': 'Neutral',
        'D': 'Drive',
    }.get(s, 'Parked')


def heading_compass(deg):
    """Return a short compass label (``N``, ``NE``, …) for a 0-360 heading."""
    try:
        deg = float(deg) % 360
    except (TypeError, ValueError):
        return ''
    points = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
    idx = int((deg + 22.5) // 45) % 8
    return points[idx]


def fan_speed_label(level):
    """Tesla fan_status is 0..7; map to a compact string."""
    try:
        level = int(level)
    except (TypeError, ValueError):
        return ''
    return f"{level}/7"


def dashcam_label(state):
    """Map ``dashcam_state`` enum to a plain-text label.

    We deliberately *don't* colour the value — green/red is reserved
    for warnings the user should act on (alarms, hard TPMS, locked-out
    PIN). Routine status toggles read better as flat text aligned in
    a single column with the rest of the menu.
    """
    if state in (None, ''):
        return 'Unavailable'
    return state


def cop_label(state):
    """Map ``cabin_overheat_protection`` enum to a plain-text label.

    Tesla returns ``Off``/``On``/``FanOnly``. Returned without colour
    for the same reason as :func:`dashcam_label`.
    """
    if state == 'FanOnly':
        return 'Fan only'
    return state or ''


def yes_no(value, yes='On', no='Off'):
    """Plain-text helper for simple bool flags.

    Returns ``yes`` or ``no`` without colouring — the menu uses red /
    green only for genuine alerts (alarm, hard-TPMS, sentry, missing
    PIN) so that those remain visually distinct.
    """
    return yes if bool(value) else no


def fmt_unix_time(ts):
    """Format a Unix-seconds timestamp as 'YYYY-MM-DD HH:MM' (local time)."""
    try:
        return datetime.fromtimestamp(int(ts)).strftime('%Y-%m-%d %H:%M')
    except (TypeError, ValueError, OSError, OverflowError):
        return str(ts)


# vehicle_config returns enum-ish strings such as ``PermanentMagnet``,
# ``FuturisFoldFlat`` or ``Turbine22Dark``. We want to surface those in
# the menu as prose ("Permanent Magnet") rather than raw API codes. The
# regex below splits at:
#   * lower→Upper boundaries           (``permanentMagnet`` → split)
#   * letter↔digit boundaries          (``Turbine22Dark``   → ``Turbine 22 Dark``)
#   * underscores / dashes             (``snake_case``      → space-separated)
#
# After splitting we Title-case each chunk while preserving recognisable
# acronyms (``EU``, ``LED``, ``AP3``, ``USB``) — Tesla mixes those into
# their config strings and lower-casing them looks worse than leaving
# them as-is.
_HUMANIZE_PATTERNS = (
    re.compile(r'([a-z])([A-Z])'),
    re.compile(r'([A-Za-z])(\d)'),
    re.compile(r'(\d)([A-Za-z])'),
)
_KEEP_ACRONYMS = {'EU', 'US', 'AP', 'AP3', 'LED', 'USB', 'PIN', 'V2', 'V3'}


def humanize_token(value):
    """Convert an API enum string to a human-readable label.

    >>> humanize_token('PermanentMagnet')   # → 'Permanent Magnet'
    >>> humanize_token('Turbine22Dark')     # → 'Turbine 22 Dark'
    >>> humanize_token('FuturisFoldFlat')   # → 'Futuris Fold Flat'
    >>> humanize_token('TeslaAP3')          # → 'Tesla AP3'
    >>> humanize_token('snake_case_thing')  # → 'Snake Case Thing'
    """
    if value is None:
        return '—'
    s = str(value)
    if not s or s == '—':
        return s
    s = s.replace('_', ' ').replace('-', ' ')
    for pat in _HUMANIZE_PATTERNS:
        s = pat.sub(r'\1 \2', s)
    parts = [p for p in s.split(' ') if p]
    out = []
    for p in parts:
        if p.upper() in _KEEP_ACRONYMS:
            out.append(p.upper())
        elif p.isdigit():
            out.append(p)
        else:
            out.append(p[:1].upper() + p[1:])
    return ' '.join(out)


# Approximate San Francisco UI Regular advance widths at 13pt — the
# default macOS menu font. Anything not listed falls back to a generic
# upper / lower / digit / other estimate. These widths only need to be
# roughly correct: as long as we land each label in the right "tab-stop
# bucket" (28pt buckets), the per-row tab maths in ``column_tabs``
# produces aligned values.
_SF_UI_PT = {
    ' ': 3.5, ':': 3.5, ';': 3.5, '.': 3.5, '-': 4.0, '_': 5.5,
    "'": 3.0, '"': 4.5, ',': 3.5, '/': 4.0, '(': 4.5, ')': 4.5,
    '!': 3.5, '?': 6.0, '°': 5.0,
    'i': 3.5, 'l': 3.5, 'I': 4.0, 'J': 4.5, 'j': 3.5,
    't': 4.5, 'f': 4.5,
    'M': 11.5, 'W': 11.5, 'm': 11.0, 'w': 10.5,
    'r': 4.5, 's': 6.0,
}

def _menu_pt(s):
    """Approximate pixel width of *s* when rendered as an NSMenu title
    in San Francisco UI Regular 13pt."""
    w = 0.0
    for c in s:
        if c in _SF_UI_PT:
            w += _SF_UI_PT[c]
        elif c.isdigit():
            w += 7.5
        elif c.isupper():
            w += 8.5
        elif c.islower():
            w += 7.0
        else:
            w += 7.0
    return w

def column_tabs(prefix_and_labels, stop_pt=28.0):
    """Compute per-row tab strings that align value columns in NSMenu.

    macOS's menu font is *proportional* San Francisco UI but
    NSAttributedString's tab stops are *pixel-based* (every 28pt by
    default). That breaks any character-based alignment scheme: two
    labels of identical character count can land in different tab-stop
    buckets, and the same number of ``\\t`` after them lands their
    values in different pixel columns.

    The fix is to compute, *for each row*, the smallest number of tabs
    that lands its value at the same target pixel column. The target
    is the first tab stop strictly past the *widest* label in the
    group, measured with the proportional-width estimator above.

    Returns a dict mapping each input string to its tab string.
    Pass *full* prefixed labels (``prefix + '--' + label``) so the
    menu's nesting indentation is included — tab stops count from the
    line's left edge.

    >>> tabs = column_tabs(['--Name:', '--Firmware:'])
    >>> [len(tabs[k]) for k in ('--Name:', '--Firmware:')]
    [2, 1]
    """
    from math import ceil
    def stop_after(label):
        # +0.001 nudges floating-point widths that happen to land
        # *exactly* on a tab stop into the next bucket — without this,
        # a value of e.g. 56.0pt would round-trip to stop 2 rather than
        # the stop the renderer would actually advance to (3).
        return max(1, int(ceil((_menu_pt(label) + 0.001) / stop_pt)))
    target = max(stop_after(p) for p in prefix_and_labels)
    return {p: '\t' * max(1, target - stop_after(p) + 1)
            for p in prefix_and_labels}


def humanize_car_type(value):
    """Map ``vehicle_config.car_type`` (``modelx`` / ``models2`` / etc.)
    to a friendly ``Model X`` / ``Model S`` / ``Model 3`` / ``Model Y`` /
    ``Cybertruck`` label. Falls back to :func:`humanize_token` for any
    new / unknown values."""
    if not value:
        return '—'
    v = str(value).lower().strip()
    aliases = {
        'models':  'Model S',
        'models2': 'Model S',
        'modelx':  'Model X',
        'model3':  'Model 3',
        'modely':  'Model Y',
        'modelr':  'Roadster',
        'roadster':'Roadster',
        'truck':   'Cybertruck',
        'cybertruck': 'Cybertruck',
    }
    return aliases.get(v, humanize_token(value))


# Pretty print sleeping time 
def sleeping_since(time=False):
    """
    Get a datetime object or a int() Epoch timestamp and return a
    pretty string like 'an hour ago', 'Yesterday', '3 months ago',
    'just now', etc
    """
    now = datetime.now()
    if type(time) is int:
        diff = now - datetime.fromtimestamp(time/1000)
    elif isinstance(time,datetime):
        diff = now - time
    elif not time:
        diff = now - now
    second_diff = diff.seconds
    day_diff = diff.days

    if day_diff < 0:
        return 'Jetlagged'

    if day_diff == 0:
        if second_diff < 10:
            return "Started sleeping a few moments ago"
        if second_diff < 60:
            return "Started sleeping "+str(second_diff) + " seconds ago"
        if second_diff < 120:
            return "Started sleeping a minute ago"
        if second_diff < 3600:
            return "Sleeping since "+str(int(second_diff / 60)) + " minutes ago"
        if second_diff < 7200:
            return "Sleeping since an hour ago"
        if second_diff < 86400:
            return "Sleeping since "+ str(int(second_diff / 3600)) + " hours ago"
    if day_diff == 1:
        return "Sleeping since Yesterday"
    if day_diff < 7:
        return "Sleeping since "+str(int(day_diff)) + " days"
    if day_diff < 31:
        return "Sleeping since "+str(int(day_diff / 7)) + " weeks"
    if day_diff < 365:
        return "Sleeping since "+str(int(day_diff / 30)) + " months"
    return "Sleeping since "+str(int(day_diff / 365)) + " year"

# Pretty print sleeping time 
def offline_since(time=False):
    """
    Get a datetime object or a int() Epoch timestamp and return a
    pretty string like 'an hour ago', 'Yesterday', '3 months ago',
    'just now', etc
    """
    now = datetime.now()
    if type(time) is int:
        diff = now - datetime.fromtimestamp(time/1000)
    elif isinstance(time,datetime):
        diff = now - time
    elif not time:
        diff = now - now
    second_diff = diff.seconds
    day_diff = diff.days

    if day_diff < 0:
        return 'Jetlagged'

    if day_diff == 0:
        if second_diff < 10:
            return "Went offline a few moments ago"
        if second_diff < 60:
            return "Went offline "+str(second_diff) + " seconds ago"
        if second_diff < 120:
            return "Went offline a minute ago"
        if second_diff < 3600:
            return "Offline since "+str(int(second_diff / 60)) + " minutes ago"
        if second_diff < 7200:
            return "Offline since an hour ago"
        if second_diff < 86400:
            return "Offline since "+ str(int(second_diff / 3600)) + " hours ago"
    if day_diff == 1:
        return "Offline since Yesterday"
    if day_diff < 7:
        return "Offline since "+str(day_diff) + " days"
    if day_diff < 31:
        return "Offline since "+str(day_diff / 7) + " weeks"
    if day_diff < 365:
        return "Offline since "+str(day_diff / 30) + " months"
    return "Offline since "+str(day_diff / 365) + " year"


# Pretty print charge time left in hours & minutes
def calculate_time_left(hours_to_full_charge):
    mins_to_full_charge = hours_to_full_charge * 60
  
    remaining_hours = int(mins_to_full_charge // 60)
    remaining_minutes = mins_to_full_charge - (remaining_hours * 60)
  
    time_left = ""

    if (mins_to_full_charge == 0):
        return '\tCalculating time remaining'

    if (remaining_hours == 0):
       time_left = '\t%d mins left' % (remaining_minutes)
    elif (remaining_hours == 1):
       time_left = '\t1 hour %d  mins left' % (remaining_minutes)
    elif (remaining_minutes == 0):
       time_left = '\t%d hours left' % (remaining_hours)
    elif (remaining_minutes == 1):
       time_left = '\t%d hours 1 min left' % (remaining_hours)
    else:
       time_left = '\t%d hours %d mins left' % (remaining_hours, remaining_minutes)

    return time_left

# Inlined Snazzy-style dark theme for the Google static-maps API. Lifted
# verbatim from the previous version of this file, just hoisted into a
# constant so we don't allocate the same multi-kilobyte string on every
# refresh.
_GOOGLE_DARK_MAP_STYLE = (
    '&style=feature:all|element:labels|visibility:on'
    '&style=feature:all|element:labels.text.fill|saturation:36|color:0x000000|lightness:40'
    '&style=feature:all|element:labels.text.stroke|visibility:on|color:0x000000|lightness:16'
    '&style=feature:all|element:labels.icon|visibility:off'
    '&style=feature:administrative|element:geometry.fill|color:0x000000|lightness:20'
    '&style=feature:administrative|element:geometry.stroke|color:0x000000|lightness:17|weight:1.2'
    '&style=feature:administrative.country|element:labels.text.fill|color:0x838383'
    '&style=feature:administrative.locality|element:labels.text.fill|color:0xc4c4c4'
    '&style=feature:administrative.neighborhood|element:labels.text.fill|color:0xaaaaaa'
    '&style=feature:landscape|element:geometry|color:0x000000|lightness:20'
    '&style=feature:poi|element:geometry|color:0x000000|lightness:21|visibility:on'
    '&style=feature:poi.business|element:geometry|visibility:on'
    '&style=feature:road.highway|element:geometry.fill|color:0x6e6e6e|lightness:0'
    '&style=feature:road.highway|element:geometry.stroke|visibility:off'
    '&style=feature:road.highway|element:labels.text.fill|color:0xffffff'
    '&style=feature:road.arterial|element:geometry|color:0x000000|lightness:18'
    '&style=feature:road.arterial|element:geometry.fill|color:0x575757'
    '&style=feature:road.arterial|element:labels.text.fill|color:0xffffff'
    '&style=feature:road.arterial|element:labels.text.stroke|color:0x2c2c2c'
    '&style=feature:road.local|element:geometry|color:0x000000|lightness:16'
    '&style=feature:road.local|element:labels.text.fill|color:0x999999'
    '&style=feature:transit|element:geometry|color:0x000000|lightness:19'
    '&style=feature:water|element:geometry|color:0x000000|lightness:17'
)


def _round_coord(value, decimals=4):
    """Stringify a lat/lon to N decimals (~11 m at 4) for cache keying."""
    try:
        return f"{round(float(value), decimals):.{decimals}f}"
    except (TypeError, ValueError):
        return str(value)


# Function to retrieve google map & sat images for a given location
def retrieve_google_maps(latitude, longitude):
    """Return ``[map_b64, sat_b64]`` PNGs for the given lat/lon.

    Both images are cached on disk (keyed by month + rounded coordinate) so
    a typical menu refresh is a zero-network operation. If the user hasn't
    configured a Google Static Maps API key yet, returns ``["", ""]`` so the
    caller can skip the map image gracefully.
    """
    google_key = get_google_static_key()
    if not google_key:
        return ["", ""]

    lat_s = _round_coord(latitude)
    lon_s = _round_coord(longitude)
    today = date.today().strftime("%Y%m")
    map_path = state_dir + f'/mytesla-location-map-{today}-{lat_s}-{lon_s}.png'
    sat_path = state_dir + f'/mytesla-location-sat-{today}-{lat_s}-{lon_s}.png'

    try:
        if os.path.getsize(map_path) > 0 and os.path.getsize(sat_path) > 0:
            with open(map_path, 'rb') as f:
                my_img1 = base64.b64encode(f.read()).decode('utf-8')
            with open(sat_path, 'rb') as f:
                my_img2 = base64.b64encode(f.read()).decode('utf-8')
            return [my_img1, my_img2]
    except OSError:
        pass

    style = _GOOGLE_DARK_MAP_STYLE if bool(DARK_MODE) else ''
    size = '&size=' + setting_map_size()
    zoom = '&zoom=17'
    common = (
        f'center={lat_s},{lon_s}'
        f'&key={google_key}'
        f'{zoom}{size}'
        f'&markers=color:red%7C{lat_s},{lon_s}'
    )
    map_url = f'https://maps.googleapis.com/maps/api/staticmap?{common}{style}'
    sat_url = f'https://maps.googleapis.com/maps/api/staticmap?{common}&maptype=hybrid'

    try:
        s = requests.Session()
        cnt1 = s.get(map_url, timeout=8).content
        cnt2 = s.get(sat_url, timeout=8).content
    except requests.RequestException:
        return ["", ""]

    try:
        with open(map_path, 'wb') as f:
            f.write(cnt1)
        with open(sat_path, 'wb') as f:
            f.write(cnt2)
    except OSError:
        pass

    return [base64.b64encode(cnt1).decode('utf-8'),
            base64.b64encode(cnt2).decode('utf-8')]


# Function to retrieve google geolocation name for a given location
def retrieve_geo_loc(latitude, longitude):
    """Reverse-geocode ``(latitude, longitude)`` with a TinyDB cache.

    Cache key is rounded coordinates (~11 m precision) so trivial GPS
    jitter doesn't churn the cache. If the user hasn't configured a Google
    Geocoding key, falls back to the raw lat/lon string.
    """
    lat_s = _round_coord(latitude)
    lon_s = _round_coord(longitude)

    try:
        Q = Query()
        hits = geolocdb.search((Q.latitude == lat_s) & (Q.longitude == lon_s))
        if hits:
            return hits[-1]['geoloc']
    except Exception:
        pass

    geocode_key = get_google_geocode_key()
    if not geocode_key:
        return f"{lat_s}, {lon_s}"

    try:
        gmaps = googleclient(geocode_key)
        result = gmaps.reverse_geocode((str(lat_s), str(lon_s)))
        if not result:
            return f"{lat_s}, {lon_s}"
        location_address = result[0]['formatted_address']
    except Exception:
        return f"{lat_s}, {lon_s}"

    if setting_location_tracking():
        try:
            geolocdb.insert({'latitude': lat_s, 'longitude': lon_s,
                             'geoloc': location_address})
            _tinydb_trim(geolocdb, GEOLOCDB_MAX_ROWS)
        except Exception:
            pass
    return location_address

# Logo for both dark mode and regular mode
def app_print_logo(extrainfo=""):
    if (extrainfo != ""): 
        print(extrainfo)
    if bool(DARK_MODE) or setting_white_logo():
        print ('|image=iVBORw0KGgoAAAANSUhEUgAAABYAAAAWCAYAAADEtGw7AAAAAXNSR0IArs4c6QAAACBjSFJNAAB6JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAAFU2lUWHRYTUw6Y29tLmFkb2JlLnhtcAAAAAAAPHg6eG1wbWV0YSB4bWxuczp4PSJhZG9iZTpuczptZXRhLyIgeDp4bXB0az0iWE1QIENvcmUgNS40LjAiPgogICA8cmRmOlJERiB4bWxuczpyZGY9Imh0dHA6Ly93d3cudzMub3JnLzE5OTkvMDIvMjItcmRmLXN5bnRheC1ucyMiPgogICAgICA8cmRmOkRlc2NyaXB0aW9uIHJkZjphYm91dD0iIgogICAgICAgICAgICB4bWxuczpkYz0iaHR0cDovL3B1cmwub3JnL2RjL2VsZW1lbnRzLzEuMS8iCiAgICAgICAgICAgIHhtbG5zOnhtcE1NPSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvbW0vIgogICAgICAgICAgICB4bWxuczpzdFJlZj0iaHR0cDovL25zLmFkb2JlLmNvbS94YXAvMS4wL3NUeXBlL1Jlc291cmNlUmVmIyIKICAgICAgICAgICAgeG1sbnM6dGlmZj0iaHR0cDovL25zLmFkb2JlLmNvbS90aWZmLzEuMC8iCiAgICAgICAgICAgIHhtbG5zOnhtcD0iaHR0cDovL25zLmFkb2JlLmNvbS94YXAvMS4wLyI+CiAgICAgICAgIDxkYzp0aXRsZT4KICAgICAgICAgICAgPHJkZjpBbHQ+CiAgICAgICAgICAgICAgIDxyZGY6bGkgeG1sOmxhbmc9IngtZGVmYXVsdCI+dGVzbGFfVF9CVzwvcmRmOmxpPgogICAgICAgICAgICA8L3JkZjpBbHQ+CiAgICAgICAgIDwvZGM6dGl0bGU+CiAgICAgICAgIDx4bXBNTTpEZXJpdmVkRnJvbSByZGY6cGFyc2VUeXBlPSJSZXNvdXJjZSI+CiAgICAgICAgICAgIDxzdFJlZjppbnN0YW5jZUlEPnhtcC5paWQ6NjFlOGM3OTktZDk2Mi00Y2JlLWFiNDItY2FmYjlmOTYxY2VlPC9zdFJlZjppbnN0YW5jZUlEPgogICAgICAgICAgICA8c3RSZWY6ZG9jdW1lbnRJRD54bXAuZGlkOjYxZThjNzk5LWQ5NjItNGNiZS1hYjQyLWNhZmI5Zjk2MWNlZTwvc3RSZWY6ZG9jdW1lbnRJRD4KICAgICAgICAgPC94bXBNTTpEZXJpdmVkRnJvbT4KICAgICAgICAgPHhtcE1NOkRvY3VtZW50SUQ+eG1wLmRpZDpCNkM1NEUzNDlERTAxMUU3QTRFNEExMTMwMUY5QkJBNTwveG1wTU06RG9jdW1lbnRJRD4KICAgICAgICAgPHhtcE1NOkluc3RhbmNlSUQ+eG1wLmlpZDpCNkM1NEUzMzlERTAxMUU3QTRFNEExMTMwMUY5QkJBNTwveG1wTU06SW5zdGFuY2VJRD4KICAgICAgICAgPHhtcE1NOk9yaWdpbmFsRG9jdW1lbnRJRD51dWlkOjI3MzY3NDg0MTg2QkRGMTE5NjZBQjM5RDc2MkZFOTlGPC94bXBNTTpPcmlnaW5hbERvY3VtZW50SUQ+CiAgICAgICAgIDx0aWZmOk9yaWVudGF0aW9uPjE8L3RpZmY6T3JpZW50YXRpb24+CiAgICAgICAgIDx4bXA6Q3JlYXRvclRvb2w+QWRvYmUgSWxsdXN0cmF0b3IgQ0MgMjAxNSAoTWFjaW50b3NoKTwveG1wOkNyZWF0b3JUb29sPgogICAgICA8L3JkZjpEZXNjcmlwdGlvbj4KICAgPC9yZGY6UkRGPgo8L3g6eG1wbWV0YT4KI5WHQwAAANVJREFUOBHtU8ENwjAMTBADdJRuACMwUjdgBEaAEcoEgQlSJmCEcJYS6VzlYVfiV0snn6/na5SqIez17xuIvReUUi7QT8AInIFezRBfwDPG+OgZlIbQL5BrT7Xf0YcK4eJpz7LMKqQ3wDSJEViXBArWJd6pl6U0mORkVyADchUBXVXVRogZuAGDCrEOWExAq2TZO1hM8CzkY06yptbgN60xJ1lTa/BMa8xJ1tQavNAac5I30vblrOtHqxG+2eENnmD5fc3lCf6YU2H0BLtO7DnE7t12Az8xb74dVbfynwAAAABJRU5ErkJggg==')
    else:
        print ('|image=iVBORw0KGgoAAAANSUhEUgAAABYAAAAWCAYAAADEtGw7AAAAGXRFWHRTb2Z0d2FyZQBBZG9iZSBJbWFnZVJlYWR5ccllPAAAA/xpVFh0WE1MOmNvbS5hZG9iZS54bXAAAAAAADw/eHBhY2tldCBiZWdpbj0i77u/IiBpZD0iVzVNME1wQ2VoaUh6cmVTek5UY3prYzlkIj8+IDx4OnhtcG1ldGEgeG1sbnM6eD0iYWRvYmU6bnM6bWV0YS8iIHg6eG1wdGs9IkFkb2JlIFhNUCBDb3JlIDUuMy1jMDExIDY2LjE0NTY2MSwgMjAxMi8wMi8wNi0xNDo1NjoyNyAgICAgICAgIj4gPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4gPHJkZjpEZXNjcmlwdGlvbiByZGY6YWJvdXQ9IiIgeG1sbnM6eG1wTU09Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC9tbS8iIHhtbG5zOnN0UmVmPSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvc1R5cGUvUmVzb3VyY2VSZWYjIiB4bWxuczp4bXA9Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC8iIHhtbG5zOmRjPSJodHRwOi8vcHVybC5vcmcvZGMvZWxlbWVudHMvMS4xLyIgeG1wTU06T3JpZ2luYWxEb2N1bWVudElEPSJ1dWlkOjI3MzY3NDg0MTg2QkRGMTE5NjZBQjM5RDc2MkZFOTlGIiB4bXBNTTpEb2N1bWVudElEPSJ4bXAuZGlkOkI2QzU0RTM0OURFMDExRTdBNEU0QTExMzAxRjlCQkE1IiB4bXBNTTpJbnN0YW5jZUlEPSJ4bXAuaWlkOkI2QzU0RTMzOURFMDExRTdBNEU0QTExMzAxRjlCQkE1IiB4bXA6Q3JlYXRvclRvb2w9IkFkb2JlIElsbHVzdHJhdG9yIENDIDIwMTUgKE1hY2ludG9zaCkiPiA8eG1wTU06RGVyaXZlZEZyb20gc3RSZWY6aW5zdGFuY2VJRD0ieG1wLmlpZDo2MWU4Yzc5OS1kOTYyLTRjYmUtYWI0Mi1jYWZiOWY5NjFjZWUiIHN0UmVmOmRvY3VtZW50SUQ9InhtcC5kaWQ6NjFlOGM3OTktZDk2Mi00Y2JlLWFiNDItY2FmYjlmOTYxY2VlIi8+IDxkYzp0aXRsZT4gPHJkZjpBbHQ+IDxyZGY6bGkgeG1sOmxhbmc9IngtZGVmYXVsdCI+dGVzbGFfVF9CVzwvcmRmOmxpPiA8L3JkZjpBbHQ+IDwvZGM6dGl0bGU+IDwvcmRmOkRlc2NyaXB0aW9uPiA8L3JkZjpSREY+IDwveDp4bXBtZXRhPiA8P3hwYWNrZXQgZW5kPSJyIj8+ux4+7QAAALlJREFUeNpi/P//PwMtABMDjcDQM5gFmyAjI2MAkLIHYgMgdsCh9wAQXwDig8B42oAhC4o8ZAwE74H4PpQ+D6XXA7EAFK9HkwOrxTAHi8ENUA3/0fB6KEYXB6ltIMZgkKv6oS4xgIqhGAYVM4CqmQ/SQ9BgbBjqbZjB54nRQ2yqeICDTXFyu4iDTbHBB3CwKTaY5KBgJLYQAmaa/9B0z0h2ziMiOKhq8AVaGfxwULiYcbQGobnBAAEGADCCwy7PWQ+qAAAAAElFTkSuQmCC')
    print('---')


# --------------------------
# Init / refresh / settings entry points
# --------------------------

def init():
    """First-run sign-in. Opens a browser to Tesla SSO and stores tokens."""
    try:
        auth = TeslaAuthenticator()
        auth.perform_login()
    except Exception as e:
        print("Error: %s" % e)
    time.sleep(0.5)


def refresh():
    """Use the refresh token in Keychain to mint a new access token."""
    try:
        auth = TeslaAuthenticator()
        auth.load_credentials()
        auth.refresh_credentials()
    except Exception as e:
        print("Error: %s" % e)
        time.sleep(0.5)


def signout():
    """Wipe Tesla tokens (but not Google API keys) from the Keychain."""
    print("Signing out — removing Tesla tokens from the macOS Keychain.")
    kr_delete("access_token")
    kr_delete("refresh_token")
    print(CGREEN + "Done. Click 'Login to tesla.com' to sign back in." + CEND)
    time.sleep(0.5)


def _prompt_secret(label, key):
    """Read a secret from the user, defaulting to whatever's in keyring.

    Echoes a `...XXXX` preview of the current value (if any) so the user can
    tell at a glance whether anything is set without exposing the full key.
    """
    current = kr_get(key, "") or ""
    suffix = f" (current ends in ...{current[-4:]})" if current else " (none set)"
    print(f"{label}{suffix}")
    print("Enter a new value, or press Return to keep the current one:")
    value = getpass.getpass("> ").strip() if key.endswith("_key") else str_input().strip()
    return value or current


def setup_keys():
    """Re-set the Google API keys in keychain. No Tesla re-login needed."""
    print("Update Google API keys stored in macOS Keychain.")
    print("(Both keys can be the same one if Static Maps + Geocoding are")
    print("both enabled on it.)\n")
    static_key = _prompt_secret(
        "Google Static Maps API key (used for the menu-bar map images)",
        "google_static_key",
    )
    if static_key:
        kr_set("google_static_key", static_key)

    geocode_key = _prompt_secret(
        "Google Geocoding API key (used for reverse-geocoding the car location)",
        "google_geocode_key",
    )
    if geocode_key:
        kr_set("google_geocode_key", geocode_key)
    print(CGREEN + "\nDone. You can close this window." + CEND)
    time.sleep(0.5)


def setup_overrides():
    """Manage the per-vehicle option-code overrides stored in keychain.

    Tesla's owner API has been returning generic / wrong option codes for
    most vehicles since 2019, so users override them here. The mapping is
    stored as a single JSON blob under the ``override_option_codes`` key.
    """
    print("Manage per-vehicle option-code overrides (stored in macOS Keychain).")
    print("")
    print("To find your option codes, log into your Tesla account and look at")
    print("the URL of the car-image picker — it ends with ?options=<comma-")
    print("separated codes>. Or run `mytesla.15m.py debug` from a terminal")
    print("after signing in to see the vehicle_id values for your account.")
    print("")

    overrides = get_override_option_codes()
    if overrides:
        print("Currently configured overrides:")
        for vid, codes in overrides.items():
            print(f"  vehicle_id={vid}  ->  {codes[:64]}{'...' if len(codes) > 64 else ''}")
    else:
        print("No overrides configured.")
    print("")

    print("Action: [a]dd/update an override, [d]elete one, [c]lear all, [q]uit?")
    choice = str_input().strip().lower() or "q"
    if choice.startswith("a"):
        print("Enter vehicle_id (digits only):")
        try:
            vid = int(str_input().strip())
        except ValueError:
            print(CRED + "Not a valid vehicle_id." + CEND)
            return
        print("Enter the comma-separated option codes for this vehicle:")
        codes = str_input().strip()
        if not codes:
            print(CRED + "No codes entered, leaving overrides unchanged." + CEND)
            return
        overrides[vid] = codes
        set_override_option_codes(overrides)
        print(CGREEN + f"Stored override for vehicle_id={vid}." + CEND)
    elif choice.startswith("d"):
        print("Enter vehicle_id to delete:")
        try:
            vid = int(str_input().strip())
        except ValueError:
            print(CRED + "Not a valid vehicle_id." + CEND)
            return
        if overrides.pop(vid, None) is None:
            print(CRED + f"No override stored for vehicle_id={vid}." + CEND)
            return
        set_override_option_codes(overrides)
        print(CGREEN + f"Removed override for vehicle_id={vid}." + CEND)
    elif choice.startswith("c"):
        kr_delete("override_option_codes")
        print(CGREEN + "All overrides cleared." + CEND)
    time.sleep(0.5)


def setup_settings():
    """Toggle the boolean settings (battery in menubar, white logo, etc.)."""
    toggles = [
        ("setting_location_tracking", "Track car location to local DB",
         setting_location_tracking()),
        ("setting_battery_menubar", "Show battery % in menubar (single car only)",
         setting_battery_menubar()),
        ("setting_white_logo", "Use white logo (recommended for Big Sur+)",
         setting_white_logo()),
        ("setting_composer_cache_high",
         "Pre-cache high-resolution car compositor images",
         setting_composer_cache_high()),
    ]
    print("Current toggles:\n")
    for i, (_key, label, value) in enumerate(toggles, start=1):
        print(f"  {i}. [{'x' if value else ' '}] {label}")
    print(f"  {len(toggles)+1}. Set Google static-map size (current: "
          f"{setting_map_size()})")
    print("")
    print("Enter a number to toggle / change, or press Return to exit:")
    choice = str_input().strip()
    if not choice:
        return
    try:
        idx = int(choice)
    except ValueError:
        print(CRED + "Not a number." + CEND)
        return
    if 1 <= idx <= len(toggles):
        key, label, value = toggles[idx - 1]
        kr_set(key, "false" if value else "true")
        print(CGREEN + f"{label} -> {'OFF' if value else 'ON'}" + CEND)
    elif idx == len(toggles) + 1:
        print("Enter new map size as WIDTHxHEIGHT (e.g. 800x600):")
        size = str_input().strip()
        if re.fullmatch(r"\d+x\d+", size):
            kr_set("setting_map_size", size)
            print(CGREEN + f"Map size set to {size}" + CEND)
        else:
            print(CRED + "Invalid size. Expected e.g. 800x600." + CEND)
    time.sleep(0.5)


def update_option_codes():
    """Download the latest community option-codes table and rebuild the JSON.

    Source is the timdorr ``optioncodes.md`` file on GitHub. We parse the
    markdown table locally — no third-party API call is involved — and
    write the result to ``~/.state/mytesla/tesla_option_codes.json`` so it
    overrides the bundle on the next refresh.
    """
    print("Fetching latest Tesla option codes from:")
    print("  " + OPTION_CODES_REMOTE_URL)
    try:
        resp = requests.get(OPTION_CODES_REMOTE_URL, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(CRED + f"Download failed: {exc}" + CEND)
        time.sleep(1)
        return

    row_re = re.compile(r"^\|\s*([A-Z0-9]+)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*$")
    out = {}
    for line in resp.text.splitlines():
        m = row_re.match(line)
        if not m:
            continue
        code, title, desc = m.group(1), m.group(2).strip(), m.group(3).strip()
        if code == "Code":
            continue
        out[code] = title or desc or "Unknown"

    if not out:
        print(CRED + "No option codes found in the downloaded markdown."
                     " Source format may have changed." + CEND)
        time.sleep(1)
        return

    try:
        with open(_USER_OPTION_CODES_PATH, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=2, sort_keys=True)
            fh.write("\n")
    except OSError as exc:
        print(CRED + f"Failed to write {_USER_OPTION_CODES_PATH}: {exc}"
              + CEND)
        time.sleep(1)
        return

    print(CGREEN + f"Wrote {len(out)} option codes to "
                   f"{_USER_OPTION_CODES_PATH}." + CEND)
    time.sleep(0.5)


# --------------------------
# The main function
# --------------------------

def main(argv):

    # CASE 1: a "settings"-style sub-command was passed (always runs in a
    # terminal, never returns to render the menu).
    if 'init' in argv:
        init(); return
    if 'refresh' in argv:
        refresh(); return
    if 'keys' in argv:
        setup_keys(); return
    if 'overrides' in argv:
        setup_overrides(); return
    if 'settings' in argv:
        setup_settings(); return
    if 'update_codes' in argv:
        update_option_codes(); return
    if 'signout' in argv:
        signout(); return

    # CASE 2: init was not called, keyring not initialized
    if bool(DARK_MODE):
        color = '#FFFFFE'
        info_color = '#C0C0C0'
    else:
        color = '#00000E'
        info_color = '#616161'


    ACCESS_TOKEN = kr_get("access_token")

    if not ACCESS_TOKEN:
       # restart in terminal calling init
       app_print_logo()
       print ('Login to tesla.com | refresh=true terminal=true shell="%s" param1="%s" color=%s' % (cmd_path, 'init', color))
       return


    # CASE 3a: check if we are online, else print nice message
    try:
        requests.get("http://www.google.com",timeout=2)
    except requests.ConnectionError:
        app_print_logo()
        print ('No internet connection | refresh=true terminal=false shell="%s" param1="%s" color=%s' % (cmd_path, 'true', color))
        return

    # Refresh the access token using the refresh token in keychain. The old
    # code called refresh() and then reused a stale ACCESS_TOKEN — re-read
    # from keychain so we use whatever refresh() just stored.
    refresh()
    ACCESS_TOKEN = kr_get("access_token") or ACCESS_TOKEN


    # CASE 3b: init was not called, keyring initialized, access code available and refreshed
    try:
        # create connection to tesla account
        c = TeslaConnection(access_token = ACCESS_TOKEN)
        vehicles = c.vehicles()
        appointments = c.appointments()
    except Exception:
       app_print_logo()
       print ('Login to tesla.com | refresh=true terminal=true shell="%s" param1="%s" color=%s' % (cmd_path, 'init', color))
       return


    # CASE 4: all ok, specific command for a specific vehicle received.
    # The first user arg (argv[1]) is the integer vehicle index; anything
    # else is a settings sub-command (already handled above) or a no-op
    # refresh ping (param1="true" from the offline handler).
    def _is_int(s):
        try:
            int(s); return True
        except (TypeError, ValueError):
            return False

    if (len(sys.argv) > 1) and not('debug' in argv) and _is_int(sys.argv[1]):
        v = vehicles[int(sys.argv[1])]


        if sys.argv[2] == "wake_up":
            print ('Waking up your car... this may take up to 30 seconds.')
            v.wake_up()
            time.sleep(30)
        else:
            if (len(sys.argv) == 2) and (sys.argv[2] != 'remote_start_drive'):
                # argv is of the form: CMD + vehicleid + command 
                v.command(sys.argv[2])
            elif sys.argv[2] == 'remote_start_drive':
                # ask for password
                print ('Enter your tesla.com password:')
                password = getpass.getpass()
                v.command(sys.argv[2],password)
                password = ''
            elif sys.argv[2] == 'navigation_request':
                # ask for address
                print ('Enter the address to set your navigation to:')
                address = str_input()
                current_timestamp = int(time.time())
                json_data = json.dumps({"type":"share_ext_content_raw", "locale":"en-US","timestamp_ms":str(current_timestamp), "value" : {"android.intent.ACTION" : "android.intent.action.SEND", "android.intent.TYPE":"text/plain", "android.intent.extra.SUBJECT":"MyTesla address","android.intent.extra.TEXT": str(address)}})
                v.command('share',json_data)
            elif sys.argv[2] == 'navigation_set_charger':
                address = location_decoder(sys.argv[3])
                current_timestamp = int(time.time())
                json_data = json.dumps({"type":"share_ext_content_raw", "locale":"en-US","timestamp_ms":str(current_timestamp), "value" : {"android.intent.ACTION" : "android.intent.action.SEND", "android.intent.TYPE":"text/plain", "android.intent.extra.SUBJECT":"MyTesla address","android.intent.extra.TEXT": str(address)}})
                print ('Setting navigation to: %s' % address)
                v.command('share',json_data)
            else:
                # argv is of the form: CMD + vehicleid + command + key:value pairs 
                json_cmd = json.dumps(dict(map(lambda x: x.split(':'),sys.argv[3:])))
                print(v.command(sys.argv[2],json_cmd))
        return


    # CASE 5: all ok, all other cases
    
    prefix = ''

    if len(vehicles) > 1:
        # Create a submenu for every vehicle
        prefix = '--'
        app_print_logo()


    # loop through vehicles, get vehicle data and print menu with relevant info       
    for i, vehicle in enumerate(vehicles):

        # if there is more than one vehicle on the account, just display the logo in the menu bar
 
        if len(vehicles) > 1:
            if vehicle['display_name'] == '':
                print ('Unnamed Tesla')
            else: 
                print ('%s' % (vehicle['display_name']))

        # get the data 
        try:
            vehicle_access = vehicle.mobile_access()
            if vehicle_access == False:
                print ('%sVehicle mobile access disabled. Click to try again. | refresh=true terminal=false shell="true" color=%s' % (prefix, color))
                continue
         
            if vehicle['in_service'] == True:
                if len(vehicles) == 1: 
                    app_print_logo()
                print ('%sVehicle in service. Click to try again. | refresh=true terminal=false shell="true" color=%s' % (prefix, color))
                continue   
 
            # get the data for the vehicle       
            vehicle_info = vehicle.vehicle_data() 
 
            if vehicle_info == None:
                app_print_logo()
                print ('%sError: Failed to get vehicle info from Tesla. Click to try again. | refresh=true terminal=false shell="true" color=%s' % (prefix, color))
                return

        except Exception as e: 
            print ('%sError: Failed to get info from Tesla. Click to try again. | refresh=true terminal=false shell="true" color=%s' % (prefix, color))
            print (e)
            return         

        # parse the data

        vehicle_name = vehicle['display_name']
        vehicle_vin  = vehicle['vin'] 

        gui_settings    = vehicle_info['gui_settings']
        charge_state    = vehicle_info['charge_state']
        climate_state   = vehicle_info['climate_state']
        drive_state     = vehicle_info['drive_state']
        vehicle_state   = vehicle_info['vehicle_state']
        vehicle_config  = vehicle_info['vehicle_config']


        recent_alerts = vehicle.recent_alerts()['recent_alerts']

        nearby_charging_sites = vehicle.nearby_charging_sites()

        temp_unit = gui_settings['gui_temperature_units']
        distance_unit='km'  
        if gui_settings['gui_distance_units'] == 'mi/hr':
            distance_unit = 'mi'


        if setting_composer_cache_high():
            # SIDE, INTERIOR, FRONT34, INTERIOR, REAR, STUD_REAR34, STUD_SIDEVIEW
            # The pre-cache loop fetches up to ~56 PNGs from Tesla's static
            # composer. Doing this synchronously would block the menu render
            # for many seconds on first run. Kick it off in a daemon thread
            # so it just trickles into the on-disk cache in the background.
            def _precache_views():
                for view in _SHOW_CAR_PICTURES_:
                    for background in ('1', '2'):
                        for size in ('512', '1024', '2048', '4096'):
                            try:
                                vehicle.compose_image(
                                    vehicle_config['car_type'],
                                    view=view, size=size,
                                    background=background,
                                )
                            except Exception:
                                pass
            try:
                import threading
                t = threading.Thread(target=_precache_views, daemon=True)
                t.start()
            except Exception:
                _precache_views()

        try:
            battery_loss_cold = int(charge_state['battery_level']) - int(charge_state['usable_battery_level'])
        except (KeyError, TypeError, ValueError):
            battery_loss_cold = 0
        battery_distance  = ""

        if (gui_settings['gui_range_display'] == 'Rated'):
           battery_distance = convert_distance(distance_unit,charge_state['battery_range'])
        else: 
           battery_distance = convert_distance(distance_unit,charge_state['ideal_battery_range'])


        # if there is only one vehicle on the account, we can optionall display the logo with extra info in the menu bar
        
        if not prefix:
            if setting_battery_menubar() and len(vehicles) == 1:
                 extrainfo = ('%s%% %s' % (charge_state['battery_level'], cold_state(battery_loss_cold)))
                 app_print_logo(extrainfo)
            else:
                 app_print_logo()


        # --------------------------------------------------
        # VEHICLE STATUS MENU
        # --------------------------------------------------

        if 'debug' in argv:
            print (vehicle.option_codes())
            print (vehicle.service_data())
            print ('>>> vehicle:\n%s\n'                 % vehicle)
            print ('>>> vehicle_info:\n%s\n'            % vehicle_info)
            print ('>>> gui_settings:\n%s\n'            % gui_settings)
            print ('>>> charge_state:\n%s\n'            % charge_state)
            print ('>>> climate_state:\n%s\n'           % climate_state)
            print ('>>> drive_state:\n%s\n'             % drive_state)
            print ('>>> vehicle_state:\n%s\n'           % vehicle_state)
            print ('>>> vehicle_config:\n%s\n'          % vehicle_config)
            print ('>>> appointments:\n%s\n'            % appointments)
            print ('>>> nearby_charging_sites\n%s\n'    % nearby_charging_sites)
            print ('>>> recent alerts:\n%s\n'           % recent_alerts)
            continue


        if vehicle['state'] == 'asleep':
            print ('%sVehicle state:\t\t\t\t\t%s. | color=%s' % (prefix, sleeping_since(vehicle_info['drive_state']['timestamp']), color))
            print ('%s--Wake up | refresh=true terminal=true shell="%s" param1=%s param2=%s color=%s' % (prefix, cmd_path, str(i), "wake_up", color))
            print ('%s---' % prefix)
           
        elif vehicle['state'] == 'offline':
            print ('%sVehicle state:\t\t\t\t\t%s. | color=%s' % (prefix, offline_since(vehicle_info['drive_state']['timestamp']), color))
            print ('%s--Connect | refresh=true terminal=true shell="%s" param1=%s param2=%s color=%s' % (prefix, cmd_path, str(i), "wake_up", color))
            print ('%s---' % prefix)

        elif vehicle['state'] == 'online':
            online_extra = ''
            try:
                if vehicle_state.get('is_user_present'):
                    online_extra = ' (driver present)'
            except Exception:
                pass
            print ('%sVehicle state:\t\t\t\t\tOnline%s | color=%s' % (prefix, online_extra, color))
            print ('%s---' % prefix)


        # --------------------------------------------------
        # STATUS BANNERS (service mode, in_service, TPMS warnings)
        # --------------------------------------------------
        # Surface anything Tesla flags as needing the user's attention
        # *before* the rest of the menu so it doesn't get buried.

        try:
            if vehicle_info.get('in_service'):
                print ('%s%sVehicle in service%s | color=%s'
                       % (prefix, CRED, CEND, color))
        except Exception:
            pass

        try:
            if vehicle_state.get('service_mode') or vehicle_state.get('service_mode_plus'):
                badge = 'Service mode' + (' Plus' if vehicle_state.get('service_mode_plus') else '')
                print ('%s%s%s active%s | color=%s'
                       % (prefix, CRED, badge, CEND, color))
        except Exception:
            pass

        try:
            tpms_warns = []
            for corner_key, corner_label in (('fl', 'FL'), ('fr', 'FR'),
                                             ('rl', 'RL'), ('rr', 'RR')):
                hard = vehicle_state.get('tpms_hard_warning_' + corner_key)
                soft = vehicle_state.get('tpms_soft_warning_' + corner_key)
                if hard:
                    tpms_warns.append(corner_label + '!')
                elif soft:
                    tpms_warns.append(corner_label)
            if tpms_warns:
                print ('%s%sTire pressure warning: %s%s | color=%s'
                       % (prefix, CRED, ', '.join(tpms_warns), CEND, color))
        except Exception:
            pass

        try:
            if charge_state.get('not_enough_power_to_heat'):
                print ('%s%sNot enough power to heat the battery%s | color=%s'
                       % (prefix, CRED, CEND, color))
        except Exception:
            pass


        # --------------------------------------------------
        # SOFTWARE UPDATE MENU 
        # --------------------------------------------------

        if (vehicle_state['software_update']['status'] == 'available'):
           print ('%sSoftware update:				%s available for installation | color=%s' % (prefix, vehicle_state['software_update']['version'], color))
           print ('%s--Install | refresh=true terminal=true shell="%s" param1=%s param2=schedule_software_update param3=%s color=%s' % (prefix, cmd_path, str(i), "offset_sec:0", color))
           print ('%s---' % prefix)
        elif (vehicle_state['software_update']['status'] == 'downloading'):
           print ('%sSoftware update:				Downloading %s (%s%%) | color=%s' % (prefix, vehicle_state['software_update']['version'], vehicle_state['software_update']['download_perc'], color))
           print ('%s---' % prefix)
        elif (vehicle_state['software_update']['status'] == 'scheduled'):
           print ('%sSoftware update:				Preparing to install %s | color=%s' % (prefix, vehicle_state['software_update']['version'], color))
           print ('%s---' % prefix)
        elif (vehicle_state['software_update']['status'] == 'installing'):
           print ('%sSoftware update:				Installing %s (%s%%) | color=%s' % (prefix, vehicle_state['software_update']['version'], vehicle_state['software_update']['install_perc'], color))
           print ('%s---' % prefix)


        # --------------------------------------------------
        # SERVICE APPOINTMENT MENU 
        # --------------------------------------------------
        try: 
           if (appointments['enabled_vins'][0]['next_appt_timestamp'] != None):
              next_appt = datetime.strptime(appointments['enabled_vins'][0]['next_appt_timestamp'],"%Y-%m-%dT%H:%M:%S%z")
              print ('%sService appoinment:\t\t\t%s | color=%s' % (prefix, next_appt.strftime("%b %d %Y, %H:%M"), color))
              print ('%s---' % prefix)
        except: 
           pass


        # --------------------------------------------------
        # BATTERY MENU 
        # --------------------------------------------------


        print ('%sBattery:\t\t\t\t\t\t%s%% %s (%s %s) | color=%s' % (prefix, charge_state['battery_level'], cold_state(battery_loss_cold), battery_distance, distance_unit, color))

        current_charge_setting = charge_state['charge_limit_soc']

        print ('%s--Charge Level set to:\t\t\t%s%% | color=%s' % (prefix, current_charge_setting, color))
        print ('%s---- 80%% | refresh=true terminal=false shell="%s" param1=%s param2=set_charge_limit param3=%s color=%s' % (prefix, cmd_path, str(i), "percent:80", color_setting(current_charge_setting,80,color,info_color)))
        print ('%s---- 80%% | refresh=true alternate=true terminal=true shell="%s" param1=%s param2=set_charge_limit param3=%s color=%s' % (prefix, cmd_path, str(i), "percent:80", color_setting(current_charge_setting,80,color,info_color)))
        print ('%s---- 85%% | refresh=true terminal=false shell="%s" param1=%s param2=set_charge_limit param3=%s color=%s' % (prefix, cmd_path, str(i), "percent:85", color_setting(current_charge_setting,85,color,info_color)))
        print ('%s---- 85%% | refresh=true alternate=true terminal=true shell="%s" param1=%s param2=set_charge_limit param3=%s color=%s' % (prefix, cmd_path, str(i), "percent:85", color_setting(current_charge_setting,85,color,info_color)))
        print ('%s---- 90%% (Default)| refresh=true terminal=false shell="%s" param1=%s param2=set_charge_limit param3=%s color=%s' % (prefix, cmd_path, str(i), "percent:90", color_setting(current_charge_setting,90,color,info_color)))
        print ('%s---- 90%% (Default)| refresh=true alternate=true terminal=true shell="%s" param1=%s param2=set_charge_limit param3=%s color=%s' % (prefix, cmd_path, str(i), "percent:90", color_setting(current_charge_setting,90,color,info_color)))
        print ('%s---- 95%% | refresh=true terminal=false shell="%s" param1=%s param2=set_charge_limit param3=%s color=%s' % (prefix, cmd_path, str(i), "percent:95", color_setting(current_charge_setting,95,color,info_color)))
        print ('%s---- 95%% | refresh=true alternate=true terminal=true shell="%s" param1=%s param2=set_charge_limit param3=%s color=%s' % (prefix, cmd_path, str(i), "percent:95", color_setting(current_charge_setting,95,color,info_color)))
        print ('%s---- 100%% (Trip only)| refresh=true terminal=false shell="%s" param1=%s param2=set_charge_limit param3=%s color=%s' % (prefix, cmd_path, str(i), "percent:100", color_setting(current_charge_setting,100,color,info_color)))
        print ('%s---- 100%% (Trip only)| refresh=true alternate=true terminal=true shell="%s" param1=%s param2=set_charge_limit param3=%s color=%s' % (prefix, cmd_path, str(i), "percent:100", color_setting(current_charge_setting,100,color,info_color)))

        print ('%s-----' % prefix)
        print ('%s--Rated battery range:\t\t\t%s %s| color=%s' % (prefix, convert_distance(distance_unit,charge_state['battery_range']),distance_unit,info_color))
        print ('%s--Ideal battery range:\t\t\t%s %s| color=%s' % (prefix, convert_distance(distance_unit,charge_state['ideal_battery_range']),distance_unit,info_color))
#        print ('%s--Estimated battery range:\t\t%s %s| color=%s' % (prefix, convert_distance(distance_unit,charge_state['est_battery_range']),distance_unit,info_color))

        print ('%s-----' % prefix)
        print ('%s--Energy added:\t\t\t\t+%s kwh| color=%s' % (prefix, charge_state['charge_energy_added'],info_color))
        print ('%s--Rated range added:\t\t\t+%s %s| color=%s' % (prefix, convert_distance(distance_unit,charge_state['charge_miles_added_rated']), distance_unit, info_color))
        print ('%s--Ideal range added:\t\t\t+%s %s| color=%s' % (prefix, convert_distance(distance_unit,charge_state['charge_miles_added_ideal']), distance_unit, info_color))
 


        # --------------------------------------------------
        # CHARGING MENU 
        # --------------------------------------------------

        if (charge_state['charging_state']=="Disconnected"):
            print ('%sCharger: \t\t\t\t\tDisconnected | color=%s' % (prefix, color))


        elif (charge_state['charging_state']=='Starting'): 
            print ('%sCharger: \t\t\t\t\tStarting | color=%s' % (prefix, color))
            print ('%s--Stop charging | refresh=true terminal=false shell="%s" param1=%s param2=charge_stop color=%s' % (prefix, cmd_path, str(i), color))
            print ('%s--Stop charging | refresh=true alternate=true terminal=true shell="%s" param1=%s param2=charge_stop color=%s' % (prefix, cmd_path, str(i), color))


        elif (charge_state['charging_state']=="Stopped"): 
            print ('%sCharger: \t\t\t\t\tStopped | color=%s' % (prefix, color))
            print ('%s--Continue charging | refresh=true terminal=false shell="%s" param1=%s param2=charge_start color=%s' % (prefix, cmd_path, str(i), color))
            print ('%s--Continue charging | refresh=true alternate=true terminal=true shell="%s" param1=%s param2=charge_start color=%s' % (prefix, cmd_path, str(i), color))


        elif (charge_state['charging_state']=="Complete"): 
            print ('%sCharger: \t\t\t\t\tCompleted | color=%s' % (prefix, color))


        elif (charge_state['charging_state']=="Charging"):
            time_left = calculate_time_left(charge_state['time_to_full_charge'])
            charger_description = "Charger:\t\t"

            # When connected to a Tesla DC fast-charger, fast_charger_brand
            # is "Tesla" and fast_charger_type is e.g. "Tesla" / "MCSingleWireCAN" /
            # "ACSingleWireCAN" / "Combo" / "MagicDock". Keep the line
            # readable by only including non-empty values.
            if (charge_state['fast_charger_present']):
               brand = (charge_state.get('fast_charger_brand') or '').strip()
               ftype = (charge_state.get('fast_charger_type')  or '').strip()
               qualifier = ' '.join(p for p in (brand, ftype)
                                    if p and p != '<invalid>').strip()
               charger_description = ("Supercharger:" if not qualifier
                                      else "Charger (%s):" % qualifier)

            print ('%s%s\t\t\t%s (%s %s/h) | color=%s' % (prefix, charger_description, time_left, convert_distance(distance_unit,charge_state['charge_rate']), distance_unit, color))
            print ('%s--Stop charging | refresh=true terminal=false shell="%s" param1=%s param2=charge_stop color=%s' % (prefix, cmd_path, str(i), color))
            print ('%s--Stop charging | refresh=true alternate=true terminal=true shell="%s" param1=%s param2=charge_stop color=%s' % (prefix, cmd_path, str(i), color))

            # Connected cable type — useful when diagnosing slow charge
            try:
                cable = charge_state.get('conn_charge_cable')
                if cable and cable != '<invalid>':
                    print ('%s--Cable:\t\t\t%s| color=%s'
                           % (prefix, cable, info_color))
            except Exception:
                pass

            # Trip planner / mid-trip charging hints
            try:
                if charge_state.get('supercharger_session_trip_planner'):
                    print ('%s--Trip Planner session | color=%s'
                           % (prefix, info_color))
                elif charge_state.get('trip_charging'):
                    print ('%s--Trip charging | color=%s'
                           % (prefix, info_color))
            except Exception:
                pass
 
            print ('%s-----' % prefix)

            if bool(charge_state['charger_pilot_current']):
               print ('%s--Maximum current:\t\t%s A| color=%s' % (prefix, charge_state['charger_pilot_current'],info_color))
               
               current_charger_amps = charge_state['charge_current_request_max']

               # Tesla API: POST /command/set_charging_amps with body
               # ``{"charging_amps": <int>}``. The previous version sent
               # ``set_charge_limit`` (which expects ``percent`` 0-100)
               # so this menu silently never worked.
               for charger_amps in range(6,25):
                   print ('%s---- %sA | refresh=true terminal=false shell="%s" param1=%s param2=set_charging_amps param3=%s color=%s' % (prefix, charger_amps, cmd_path, str(i), 'charging_amps:'+str(charger_amps), color_setting(current_charger_amps,charger_amps,color,info_color)))
                   print ('%s---- %sA | refresh=true alternate=true terminal=true shell="%s" param1=%s param2=set_charging_amps param3=%s color=%s' % (prefix, charger_amps, cmd_path, str(i), 'charging_amps:'+str(charger_amps), color_setting(current_charger_amps,charger_amps,color,info_color)))
            else:
               print ('%s--Maximum current:\t\tNo information| color=%s' % (prefix,info_color))
            print ('%s--Actual current:\t\t%s A| color=%s' % (prefix, charge_state['charger_actual_current'],info_color))
            print ('%s--Power:\t\t\t\t%s Kw| color=%s' % (prefix, charge_state['charger_power'],info_color))
            print ('%s--Voltage:\t\t\t\t%s V| color=%s' % (prefix, charge_state['charger_voltage'],info_color))
            print ('%s--Phases:\t\t\t\t%s| color=%s' % (prefix, charge_state['charger_phases'],info_color))


        else:
            print ('%sCharger: \t\t\t\t\t%s | color=%s' % (prefix, charge_state['charging_state'],color))

        # --------------------------------------------------
        # SCHEDULED CHARGING / DEPARTURE
        # --------------------------------------------------
        # Tesla exposes either ``scheduled_charging_mode`` ("StartAt" /
        # "DepartBy" / "Off") + a Unix-second start/departure timestamp.

        try:
            sched_mode = charge_state.get('scheduled_charging_mode')
            if sched_mode and sched_mode != 'Off':
                if sched_mode == 'DepartBy':
                    when = charge_state.get('scheduled_departure_time')
                    label = 'Depart by:\t\t' + (fmt_unix_time(when) if when else 'set')
                else:
                    when = charge_state.get('scheduled_charging_start_time')
                    label = 'Charge starts:\t' + (fmt_unix_time(when) if when else 'set')
                print ('%s%s | color=%s' % (prefix, label, info_color))
                if charge_state.get('scheduled_charging_pending'):
                    print ('%s-- (pending) | color=%s' % (prefix, info_color))
                if charge_state.get('preconditioning_enabled'):
                    times = charge_state.get('preconditioning_times', '')
                    extra = ' (' + times + ')' if times else ''
                    print ('%s--Preconditioning enabled%s | color=%s'
                           % (prefix, extra, info_color))
                if charge_state.get('off_peak_charging_enabled'):
                    times = charge_state.get('off_peak_charging_times', '')
                    extra = ' (' + times + ')' if times else ''
                    print ('%s--Off-peak only%s | color=%s'
                           % (prefix, extra, info_color))
        except Exception:
            pass

        print ('%s---' % prefix)

        # --------------------------------------------------
        # VEHICLE STATE MENU 
        # --------------------------------------------------

        # Car & Alarm overview
        
        sentry_available = False
        sentry_description = ""
        sentry_state = 'off'

        try:
            if (vehicle_state['sentry_mode'] == True):
                sentry_available = True
                sentry_description = CGREEN+'(Sentry On)'+CEND
                sentry_state = 'on'
            else: 
                sentry_available = True
                sentry_description = CRED+'(Sentry Off)'+CEND
                sentry_state = 'off'
        except:
            pass
  
        print ('%sVehicle security:\t\t\t\t%s %s | color=%s' % (prefix, lock_state(vehicle_state['locked']), sentry_description, color))

        if bool(vehicle_state['locked']):
            print ('%s--%s | refresh=true terminal=false shell="%s" param1=%s param2=door_unlock color=%s' % (prefix, CRED+'Unlock'+CEND, cmd_path, str(i), color))
            print ('%s--%s | refresh=true alternate=true terminal=true shell="%s" param1=%s param2=door_unlock color=%s' % (prefix, CRED+'Unlock'+CEND, cmd_path, str(i), color))
            if bool(sentry_available): 
                print ('%s-----' % (prefix))
                if (sentry_state == 'off'):
                   print ('%s--%s | refresh=true terminal=false shell="%s" param1=%s param2=set_sentry_mode param3="on:true" color=%s' % (prefix, CGREEN+'Turn on Sentry'+CEND, cmd_path, str(i), color))
                   print ('%s--%s | refresh=true alternate=true terminal=true shell="%s" param1=%s param2=set_sentry_mode param3="on:true" color=%s' % (prefix, CGREEN+'Turn on Sentry'+CEND, cmd_path, str(i), color))
                else:
                   print ('%s--%s | refresh=true terminal=false shell="%s" param1=%s param2=set_sentry_mode param3="on:false" color=%s' % (prefix, CRED+'Turn off Sentry'+CEND, cmd_path, str(i), color))
                   print ('%s--%s | refresh=true alternate=true terminal=true shell="%s" param1=%s param2=set_sentry_mode param3="on:false" color=%s' % (prefix, CRED+'Turn off Sentry'+CEND, cmd_path, str(i), color))
 
        else:
            print ('%s--%s | refresh=true terminal=false shell="%s" param1=%s param2=door_lock color=%s' % (prefix, CGREEN+'Lock'+CEND, cmd_path, str(i), color))
            print ('%s--%s | refresh=true alternate=true terminal=true shell="%s" param1=%s param2=door_lock color=%s' % (prefix, CGREEN+'Lock'+CEND, cmd_path, str(i), color))


        # Door overview

        print ('%s-----' % prefix)
        print ('%s--Driver front door:\t\t\t\t%s | color=%s' % (prefix, door_state(vehicle_state['df']),info_color))
        print ('%s--Driver rear door:\t\t\t\t%s | color=%s' % (prefix, door_state(vehicle_state['dr']),info_color))
        print ('%s--Passenger front door:\t\t\t%s | color=%s' % (prefix, door_state(vehicle_state['pf']),info_color))
        print ('%s--Passenger rear door:\t\t\t%s | color=%s' % (prefix, door_state(vehicle_state['pr']),info_color))
        print ('%s-----' % prefix)


        # Window overview
        
        print ('%s--Driver front window:\t\t\t%s| color=%s' % (prefix, window_state(vehicle_state['fd_window']),info_color))
        if (vehicle_state['fd_window'] == 0):
            print ('%s----Open | refresh=true terminal=false shell="%s" param1=%s param2=window_control param3=%s param4=%s param5=%s color=%s' % (prefix, cmd_path, str(i), 'command:vent', 'lat:0', 'lon:0', color))
            print ('%s----Open | refresh=true alternate=true terminal=true shell="%s" param1=%s param2=window_control param3=%s param4=%s param5=%s color=%s' % (prefix, cmd_path, str(i), 'command:vent', 'lat:0', 'lon:0', color))
        else:
            print ('%s----Close (Not available) | refresh=true terminal=false shell="%s" param1=%s param2=window_control param3=%s param4=%s param5=%s color=%s' % (prefix, cmd_path, str(i), 'command:close', 'lat:0', 'lon:0', info_color))
            print ('%s----Close (Not available) | refresh=true alternate=true terminal=true shell="%s" param1=%s param2=window_control param3=%s param4=%s param5=%s color=%s' % (prefix, cmd_path, str(i), 'command:close', 'lat:0', 'lon:0', info_color))
        print ('%s--Driver rear window:\t\t\t%s| color=%s' % (prefix, window_state(vehicle_state['rd_window']),info_color))
        if (vehicle_state['rd_window'] == 0):
            print ('%s----Open | refresh=true terminal=false shell="%s" param1=%s param2=window_control param3=%s param4=%s param5=%s color=%s' % (prefix, cmd_path, str(i), 'command:vent', 'lat:0', 'lon:0', color))
            print ('%s----Open | refresh=true alternate=true terminal=true shell="%s" param1=%s param2=window_control param3=%s param4=%s param5=%s color=%s' % (prefix, cmd_path, str(i), 'command:vent', 'lat:0', 'lon:0', color))
        else:
            print ('%s----Close (Not available) | refresh=true terminal=false shell="%s" param1=%s param2=window_control param3=%s param4=%s param5=%s color=%s' % (prefix, cmd_path, str(i), 'command:close', 'lat:0', 'lon:0', info_color))
            print ('%s----Close (Not available) | refresh=true alternate=true terminal=true shell="%s" param1=%s param2=window_control param3=%s param4=%s param5=%s color=%s' % (prefix, cmd_path, str(i), 'command:close', 'lat:0', 'lon:0', info_color))
 
        print ('%s--Passenger front window:\t\t%s| color=%s' % (prefix, window_state(vehicle_state['fp_window']),info_color))
        if (vehicle_state['fp_window'] == 0):
            print ('%s----Open | refresh=true terminal=false shell="%s" param1=%s param2=window_control param3=%s param4=%s param5=%s color=%s' % (prefix, cmd_path, str(i), 'command:vent', 'lat:0', 'lon:0', color))
            print ('%s----Open | refresh=true alternate=true terminal=true shell="%s" param1=%s param2=window_control param3=%s param4=%s param5=%s color=%s' % (prefix, cmd_path, str(i), 'command:vent', 'lat:0', 'lon:0', color))
        else:
            print ('%s----Close (Not available) | refresh=true terminal=false shell="%s" param1=%s param2=window_control param3=%s param4=%s param5=%s color=%s' % (prefix, cmd_path, str(i), 'command:close', 'lat:0', 'lon:0', info_color))
            print ('%s----Close (Not available) | refresh=true alternate=true terminal=true shell="%s" param1=%s param2=window_control param3=%s param4=%s param5=%s color=%s' % (prefix, cmd_path, str(i), 'command:close', 'lat:0', 'lon:0', info_color))
        print ('%s--Passenger rear window:\t\t%s| color=%s' % (prefix, window_state(vehicle_state['rp_window']),info_color))
        if (vehicle_state['rp_window'] == 0):
            print ('%s----Open | refresh=true terminal=false shell="%s" param1=%s param2=window_control param3=%s param4=%s param5=%s color=%s' % (prefix, cmd_path, str(i), 'command:vent', 'lat:0', 'lon:0', color))
            print ('%s----Open | refresh=true alternate=true terminal=true shell="%s" param1=%s param2=window_control param3=%s param4=%s param5=%s color=%s' % (prefix, cmd_path, str(i), 'command:vent', 'lat:0', 'lon:0', color))
        else:
            print ('%s----Close (Not available) | refresh=true terminal=false shell="%s" param1=%s param2=window_control param3=%s param4=%s param5=%s color=%s' % (prefix, cmd_path, str(i), 'command:close', 'lat:0', 'lon:0', info_color))
            print ('%s----Close (Not available) | refresh=true alternate=true terminal=true shell="%s" param1=%s param2=window_control param3=%s param4=%s param5=%s color=%s' % (prefix, cmd_path, str(i), 'command:close', 'lat:0', 'lon:0', info_color))
        print ('%s-----' % prefix)


        # Sunroof overview

        try:
            if bool(vehicle_config['sun_roof_installed']):
                print ('%s-----' % prefix)
                print ('%s--Sun roof open: %s%% | color=%s' % (prefix, vehicle_state['sun_roof_percent_open'], color))
                print ('%s---- 0%% (Closed)| refresh=true terminal=false shell="%s" param1=%s param2=sun_roof_control param3=%s color=%s' % (prefix, cmd_path, str(i), "percent:0", color))
                print ('%s---- 0%% (Closed)| refresh=true alternate=true terminal=true shell="%s" param1=%s param2=sun_roof_control param3=%s color=%s' % (prefix, cmd_path, str(i), "percent:0", color))
                print ('%s---- 15%% (Vent)| refresh=true terminal=false shell="%s" param1=%s param2=sun_roof_control param3=%s color=%s' % (prefix, cmd_path, str(i), "percent:15", color))
                print ('%s---- 15%% (Vent)| refresh=true alternate=true terminal=true shell="%s" param1=%s param2=sun_roof_control param3=%s color=%s' % (prefix, cmd_path, str(i), "percent:15", color))
                print ('%s---- 80%% (Comfort)| refresh=true terminal=false shell="%s" param1=%s param2=sun_roof_control param3=%s color=%s' % (prefix, cmd_path, str(i), "percent:80", color))
                print ('%s---- 80%% (Comfort)| refresh=true alternate=true terminal=true shell="%s" param1=%s param2=sun_roof_control param3=%s color=%s' % (prefix, cmd_path, str(i), "percent:80", color))
                print ('%s---- 100%% (Open)| refresh=true terminal=false shell="%s" param1=%s param2=sun_roof_control param3=%s color=%s' % (prefix, cmd_path, str(i), "percent:100", color))
                print ('%s---- 100%% (Open)| refresh=true alternate=true terminal=true shell="%s" param1=%s param2=sun_roof_control param3=%s color=%s' % (prefix, cmd_path, str(i), "percent:100", color))
        except:
           # API change going to firmware 2018.4
           pass
 

        # Trunk and frunk overview

        print ('%s--Front trunk:\t\t\t\t\t%s| color=%s' % (prefix, door_state(vehicle_state['ft']),color))
        if (bool(vehicle_state['ft'])):
            print ('%s----Close | refresh=true terminal=false shell="%s" param1=%s param2=actuate_trunk param3=%s color=%s' % (prefix, cmd_path, str(i), "which_trunk:front", color))
            print ('%s----Close | refresh=true alternate=true terminal=true shell="%s" param1=%s param2=actuate_trunk param3=%s color=%s' % (prefix, cmd_path, str(i), "which_trunk:front", color))
        else: 
            print ('%s----Open | refresh=true terminal=false shell="%s" param1=%s param2=actuate_trunk param3=%s color=%s' % (prefix, cmd_path, str(i), "which_trunk:front", color))
            print ('%s----Open | refresh=true alternate=true terminal=true  shell="%s" param1=%s param2=actuate_trunk param3=%s color=%s' % (prefix, cmd_path, str(i), "which_trunk:front", color))

        print ('%s--Rear trunk:\t\t\t\t\t%s| color=%s' % (prefix, door_state(vehicle_state['rt']),info_color))
        if (bool(vehicle_state['rt'])):
            print ('%s----Close | refresh=true terminal=false shell="%s" param1=%s param2=actuate_trunk param3=%s color=%s' % (prefix, cmd_path, str(i), "which_trunk:rear", color))
            print ('%s----Close | refresh=true alternate=true terminal=true shell="%s" param1=%s param2=actuate_trunk param3=%s color=%s' % (prefix, cmd_path, str(i), "which_trunk:rear", color))
        else: 
            print ('%s----Open | refresh=true terminal=false shell="%s" param1=%s param2=actuate_trunk param3=%s color=%s' % (prefix, cmd_path, str(i), "which_trunk:rear", color))
            print ('%s----Open | refresh=true alternate=true terminal=true shell="%s" param1=%s param2=actuate_trunk param3=%s color=%s' % (prefix, cmd_path, str(i), "which_trunk:rear", color))
        
        charge_port_defrost = ""
        
        try:
            if (charge_state['charge_port_cold_weather_mode']):
                charge_port_defrost = CBLUE + '(defrosting)' + CEND
        except:
            pass
 
        print ('%s--Charge port:\t\t\t\t\t%s %s| color=%s' % (prefix, port_state(charge_state['charge_port_door_open'],charge_state['charge_port_latch']), charge_port_defrost, color))
        if (bool(charge_state['charge_port_door_open'])) and (not(charge_state['charge_port_latch'] == 'Engaged')):
            print ('%s----Close | refresh=true terminal=false shell="%s" param1=%s param2=charge_port_door_close color=%s' % (prefix, cmd_path, str(i), color))
            print ('%s----Close | refresh=true alternate=true terminal=true shell="%s" param1=%s param2=charge_port_door_close color=%s' % (prefix, cmd_path, str(i), color))
        if (not(bool(charge_state['charge_port_door_open']))):
            print ('%s----Open | refresh=true terminal=false shell="%s" param1=%s param2=charge_port_door_open color=%s' % (prefix, cmd_path, str(i), color))
            print ('%s----Open | refresh=true alternate=true terminal=true shell="%s" param1=%s param2=charge_port_door_open color=%s' % (prefix, cmd_path, str(i), color))

        # Live driving info: speed + shift + heading + power.
        # ``speed`` is None while parked, an integer while driving.
        # ``shift_state`` is 'P'/'R'/'N'/'D' when in motion, None when
        # parked/asleep. ``heading`` is 0-360. ``power`` is kW (negative
        # while regen-braking).
        ds_speed   = drive_state.get('speed')
        ds_shift   = drive_state.get('shift_state')
        ds_heading = drive_state.get('heading')
        ds_power   = drive_state.get('power')

        if bool(ds_speed):
            print ('%sVehicle speed:\t\t\t\t%s %s/h| color=%s'
                   % (prefix,
                      convert_distance(distance_unit, ds_speed),
                      distance_unit, color))
        else:
            print ('%sVehicle speed:\t\t\t\t%s| color=%s'
                   % (prefix, shift_state_label(ds_shift), color))

        try:
            if ds_shift in ('R', 'N', 'D') or bool(ds_speed):
                print ('%s--Gear:\t\t\t%s| color=%s'
                       % (prefix, shift_state_label(ds_shift), info_color))
        except Exception:
            pass

        try:
            if ds_heading is not None:
                cardinal = heading_compass(ds_heading)
                heading_label = ('%d°' % int(ds_heading)) + (' ' + cardinal if cardinal else '')
                print ('%s--Heading:\t\t%s| color=%s'
                       % (prefix, heading_label, info_color))
        except Exception:
            pass

        try:
            if ds_power not in (None, 0):
                power_color = info_color
                power_label = '%d kW' % int(ds_power)
                if int(ds_power) < 0:
                    power_label += ' (regen)'
                print ('%s--Power:\t\t\t%s| color=%s'
                       % (prefix, power_label, power_color))
        except Exception:
            pass
 
        

        # Vehicle location overview

        car_location_address = retrieve_geo_loc(drive_state['latitude'],drive_state['longitude'])

        print ('%s-----' % prefix)
        print ('%s--Location:\t\t%s| color=%s' % (prefix, car_location_address, color))
        print ('%s-----' % prefix)
        print ('%s--Lat:\t\t\t%s| color=%s' % (prefix, drive_state['latitude'], info_color))
        print ('%s--Lon:\t\t\t%s| color=%s' % (prefix, drive_state['longitude'], info_color))
    
        try: 
            active_route_destination = drive_state['active_route_destination']
            # geocode_map = gmaps.geocode(urllib.parse.quote(str(active_route_destination)))
            # geocode_map_lat = geocode_map[0]['geometry']['location']['lat']
            # geocode_map_lng = geocode_map[0]['geometry']['location']['lng']
            
            # vehicle_destination = retrieve_google_maps(str(geocode_map_lat),str(geocode_map_lng))
            # vehicle_destination_map = vehicle_destination[0]
            # vehicle_destination_sat = vehicle_destination[1]

            print ('%s-----' % prefix)
            print ('%s--Destination:\t%s| color=%s' % (prefix, active_route_destination, color))
            # print ('%s----|image=%s href="https://maps.google.com?q=%s,%s" color=%s' % (prefix, vehicle_destination_map, geocode_map_lat, geocode_map_lng, color))
            # print ('%s----|image=%s alternate=true href="https://maps.google.com?q=%s,%s" color=%s' % (prefix, vehicle_destination_sat, geocode_map_lat, geocode_map_lng, color))

            try: 
                destination_minutes_left = str(int(drive_state['active_route_minutes_to_arrival']))
                destination_miles_left = str(drive_state['active_route_miles_to_arrival'])
                print ('%s-----' % prefix)
                print ('%s--Time left:\t%s min| color=%s' % (prefix, destination_minutes_left, info_color))
                print ('%s--Distance:\t%s km| color=%s' % (prefix, convert_distance(distance_unit, destination_miles_left), info_color))
            except:
                pass
        except:
            pass

        print ('%s---' % prefix)
       
        # --------------------------------------------------
        # VEHICLE MAP MENU 
        # --------------------------------------------------

        google_maps = retrieve_google_maps(str(drive_state['latitude']),str(drive_state['longitude']))
        vehicle_location_map = google_maps[1]
        vehicle_location_sat = google_maps[0]

        print ('%s|image=%s href="https://maps.google.com?q=%s,%s" color=%s' % (prefix, vehicle_location_map, drive_state['latitude'],drive_state['longitude'],color))
        print ('%s|image=%s alternate=true href="https://maps.google.com?q=%s,%s" color=%s' % (prefix, vehicle_location_sat, drive_state['latitude'],drive_state['longitude'],color))

        print ('%s---' % prefix)

        # --------------------------------------------------
        # CLIMATE STATE MENU 
        # --------------------------------------------------
   
        try:
            print ('%sInside temp:\t\t\t\t\t%.1f° %s| color=%s' % (prefix, convert_temp(temp_unit,climate_state['inside_temp']),temp_unit,color))
        except:
            print ('%sInside temp:\t\t\t\t\tUnavailable| color=%s' % (prefix,color))
        if climate_state['is_climate_on']:
            print ('%s--Turn off airco | refresh=true terminal=false shell="%s" param1=%s param2=auto_conditioning_stop color=%s' % (prefix, cmd_path, str(i), color))
            print ('%s--Turn off airco | refresh=true alternate=true terminal=true shell="%s" param1=%s param2=auto_conditioning_stop color=%s' % (prefix, cmd_path, str(i), color))
        else:
            print ('%s--Turn on airco | refresh=true terminal=false shell="%s" param1=%s param2=auto_conditioning_start color=%s' % (prefix, cmd_path, str(i), color))
            print ('%s--Turn on airco | refresh=true alternate=true terminal=true shell="%s" param1=%s param2=auto_conditioning_start color=%s' % (prefix, cmd_path, str(i), color))
        
        if climate_state['is_front_defroster_on']:
            print ('%s--Turn off window defrost | refresh=true terminal=false shell="%s" param1=%s param2=set_preconditioning_max param3=%s color=%s' % (prefix, cmd_path, str(i), 'on:false', color))
            print ('%s--Turn off window defrost | refresh=true alternate=true terminal=true shell="%s" param1=%s param2=set_preconditioning_max param3=%s color=%s' % (prefix, cmd_path, str(i), 'on:false', color))
        else:
            print ('%s--Turn on window defrost | refresh=true terminal=false shell="%s" param1=%s param2=set_preconditioning_max param3=%s color=%s' % (prefix, cmd_path, str(i), 'on:true', color))
            print ('%s--Turn on window defrost | refresh=true alternate=true terminal=true shell="%s" param1=%s param2=set_preconditioning_max param3=%s color=%s' % (prefix, cmd_path, str(i), 'on:true', color))

        print ('%s-----' % prefix)

        # Per-row tab counts so every value lands on the same NSMenu
        # pixel tab-stop regardless of label length. ``_ct`` is a small
        # local helper that picks the right number of tabs for each row
        # within the climate submenu group.
        _clim_prefix = prefix + '--'
        _clim_labels = ['Airco set to:', 'Dog Mode:',
                        'Steering heating:', 'Overheat protect:',
                        'Bioweapon defense:', 'Mirror heaters:',
                        'Wiper heater:', 'Preconditioning:', 'Fan:']
        _clim_tabs = column_tabs([_clim_prefix + l for l in _clim_labels])
        def _ct(lbl):
            return _clim_tabs[_clim_prefix + lbl]

        current_temp_setting = convert_temp(temp_unit,climate_state['driver_temp_setting'])

        print ('%s--Airco set to:%s%.1f° %s | color=%s' % (prefix, _ct('Airco set to:'), current_temp_setting, temp_unit, color))
        
        for temperature in range(18,26): 
            print ('%s---- %s° %s| refresh=true terminal=false shell="%s" param1=%s param2=set_temps param3=%s param4=%s color=%s' % (prefix, convert_temp(temp_unit,temperature), temp_unit, cmd_path, str(i), "driver_temp:"+str(temperature),"passenger_temp:"+str(temperature), color_setting(current_temp_setting,temperature,color,info_color)))
            print ('%s---- %s° %s| refresh=true alternate=true terminal=true shell="%s" param1=%s param2=set_temps param3=%s param4=%s color=%s' % (prefix, convert_temp(temp_unit,temperature), temp_unit, cmd_path, str(i), "driver_temp:"+str(temperature),"passenger_temp:"+str(temperature), color_setting(current_temp_setting,temperature,color,info_color)))
        

        # TODO: Dog Mode API unpublished - to be verified

        if climate_state['climate_keeper_mode'] == 'dog':
            print ('%s--Dog Mode:%sOn | color=%s' % (prefix, _ct('Dog Mode:'), color))
            print ('%s----Turn off | refresh=true terminal=false shell="%s" param1=%s param2=set_climate_keeper param3="on:false" color=%s' % (prefix, cmd_path, str(i), color))
            print ('%s----Turn off | refresh=true alternate=true terminal=true shell="%s" param1=%s param2=set_climate_keeper param3="on:false" color=%s' % (prefix, cmd_path, str(i), color))
        else:
            print ('%s--Dog Mode:%sOff | color=%s' % (prefix, _ct('Dog Mode:'), color))
            print ('%s----Turn on | refresh=true terminal=false shell="%s" param1=%s param2=set_climate_keeper param3="on:true" color=%s' % (prefix, cmd_path, str(i), color))
            print ('%s----Turn on | refresh=true alternate=true terminal=true shell="%s" param1=%s param2=set_climate_keeper param3="on:true" color=%s' % (prefix, cmd_path, str(i), color))


        print ('%s-----' % prefix)
        print ('%s--Seat heating | color=%s' % (prefix, color))
          

        # Seat heating: align all six seat labels in one column. Tab
        # padding is computed dynamically using ``column_target`` so the
        # values land in the same place regardless of how long the label
        # is ("Driver:" vs "Third row right:").
        seats = [(0, 'Driver:',           'seat_heater_left'),
                 (1, 'Passenger:',        'seat_heater_right'),
                 (2, 'Rear left:',        'seat_heater_rear_left'),
                 (3, 'Rear center:',      'seat_heater_rear_center'),
                 (4, 'Rear right:',       'seat_heater_rear_right'),
                 (5, 'Third row left:',   'seat_heater_third_row_left'),
                 (6, 'Third row right:',  'seat_heater_third_row_right')]
        seat_prefix = prefix + '----'
        seat_tabs   = column_tabs([seat_prefix + n for _, n, _ in seats])
        for seat_nr, seat_name, seat_api in seats:
            try:
                current_seat_setting = climate_state[seat_api]
                print ('%s%s%s%s | color=%s'
                       % (seat_prefix, seat_name,
                          seat_tabs[seat_prefix + seat_name],
                          seat_state(current_seat_setting), color))
                for seat_setting in range(0,4):
                    print ('%s------ %s | refresh=true terminal=false shell="%s" param1=%s param2=remote_seat_heater_request param3=%s param4=%s color=%s' % (prefix, seat_state(seat_setting), cmd_path, str(i), "heater:"+str(seat_nr),"level:"+str(seat_setting), color_setting(current_seat_setting,seat_setting,color,info_color)))
                    print ('%s------ %s | refresh=true alternate=true terminal=true shell="%s" param1=%s param2=remote_seat_heater_request param3=%s param4=%s color=%s' % (prefix, seat_state(seat_setting), cmd_path, str(i), "heater:"+str(seat_nr),"level:"+str(seat_setting), color_setting(current_seat_setting,seat_setting,color,info_color)))
            except: 
                pass


        try:
           if climate_state['steering_wheel_heater']: 
              print ('%s--Steering heating:%sOn | color=%s' % (prefix, _ct('Steering heating:'), color))
              print ('%s----Turn off | refresh=true terminal=false shell="%s" param1=%s param2=remote_steering_wheel_heater_request param3="on:false" color=%s' % (prefix, cmd_path, str(i), color))
              print ('%s----Turn off | refresh=true alternate=true terminal=true shell="%s" param1=%s param2=remote_steering_wheel_heater_request param3="on:false" color=%s' % (prefix, cmd_path, str(i), color))
           else:
              print ('%s--Steering heating:%sOff | color=%s' % (prefix, _ct('Steering heating:'), color))
              print ('%s----Turn on | refresh=true terminal=false shell="%s" param1=%s param2=remote_steering_wheel_heater_request param3="on:true" color=%s' % (prefix, cmd_path, str(i), color))
              print ('%s----Turn on | refresh=true alternate=true terminal=true shell="%s" param1=%s param2=remote_steering_wheel_heater_request param3="on:true" color=%s' % (prefix, cmd_path, str(i), color))
        except:
            pass

        try:
            if climate_state['is_front_defroster_on']:
                print ('%s-- Front window defrosting | color=%s' % (prefix, color))
        except:
            pass
        try:
            if climate_state['is_rear_defroster_on']:
                print ('%s-- Rear window defrosting | color=%s' % (prefix, color))
        except:
            pass
        try:
            if charge_state['battery_heater_on']:
                print ('%s--Battery heating | color=%s' % (prefix, color))
        except:
            pass

        # Cabin Overheat Protection — submenu mirrors the existing
        # ``Steering heating`` convention: a single primary action whose
        # *label* describes the resulting state ("Turn on" when currently
        # off, "Turn off" when currently on). When ``FanOnly`` is
        # supported we surface that as a secondary, *non-primary* row so
        # the user can opt in without breaking the main toggle pattern.
        # Tesla's enum values are ``Off`` / ``On`` / ``FanOnly``.
        try:
            cop_state    = climate_state.get('cabin_overheat_protection')
            supports_fan = climate_state.get(
                'supports_fan_only_cabin_overheat_protection')
            if cop_state is not None:
                cop_off      = (cop_state == 'Off')
                primary_lbl  = 'Turn on' if cop_off else 'Turn off'
                primary_arg  = 'on:true' if cop_off else 'on:false'
                primary_fan  = 'fan_only:false'
                print ('%s--Overheat protect:%s%s | color=%s'
                       % (prefix, _ct('Overheat protect:'), cop_label(cop_state), color))
                print ('%s----%s | refresh=true terminal=false shell="%s" param1=%s param2=set_cabin_overheat_protection param3=%s param4=%s color=%s'
                       % (prefix, primary_lbl, cmd_path, str(i),
                          primary_arg, primary_fan, color))
                print ('%s----%s | refresh=true alternate=true terminal=true shell="%s" param1=%s param2=set_cabin_overheat_protection param3=%s param4=%s color=%s'
                       % (prefix, primary_lbl, cmd_path, str(i),
                          primary_arg, primary_fan, color))
                # "Fan only" mode: only meaningful while the car supports
                # it, and only when we'd actually change something
                # (i.e. we're not already in FanOnly).
                if supports_fan and cop_state != 'FanOnly':
                    print ('%s----Fan only | refresh=true terminal=false shell="%s" param1=%s param2=set_cabin_overheat_protection param3=on:true param4=fan_only:true color=%s'
                           % (prefix, cmd_path, str(i), info_color))
                    print ('%s----Fan only | refresh=true alternate=true terminal=true shell="%s" param1=%s param2=set_cabin_overheat_protection param3=on:true param4=fan_only:true color=%s'
                           % (prefix, cmd_path, str(i), info_color))
        except Exception:
            pass

        # Bioweapon Defense Mode (Model S/X only) — simple toggle.
        try:
            if 'bioweapon_mode' in climate_state:
                bio = bool(climate_state.get('bioweapon_mode'))
                print ('%s--Bioweapon defense:%s%s | color=%s'
                       % (prefix, _ct('Bioweapon defense:'), yes_no(bio), color))
                target = 'on:false' if bio else 'on:true'
                label  = 'Turn off' if bio else 'Turn on'
                print ('%s----%s | refresh=true terminal=false shell="%s" param1=%s param2=set_bioweapon_mode param3=%s param4=manual_override:true color=%s'
                       % (prefix, label, cmd_path, str(i), target, color))
                print ('%s----%s | refresh=true alternate=true terminal=true shell="%s" param1=%s param2=set_bioweapon_mode param3=%s param4=manual_override:true color=%s'
                       % (prefix, label, cmd_path, str(i), target, color))
        except Exception:
            pass

        # Auxiliary heaters & live status — display-only, plain text.
        # Tab counts are tuned so the values land in the same column as
        # ``Dog Mode:`` and ``Steering heating:`` above.
        try:
            if climate_state.get('side_mirror_heaters'):
                print ('%s--Mirror heaters:%sOn | color=%s' % (prefix, _ct('Mirror heaters:'), color))
            if climate_state.get('wiper_blade_heater'):
                print ('%s--Wiper heater:%sOn | color=%s' % (prefix, _ct('Wiper heater:'), color))
            if climate_state.get('is_preconditioning'):
                print ('%s--Preconditioning:%sActive | color=%s' % (prefix, _ct('Preconditioning:'), color))
            fan = climate_state.get('fan_status')
            if fan not in (None, 0):
                print ('%s--Fan:%s%s | color=%s'
                       % (prefix, _ct('Fan:'), fan_speed_label(fan), color))
        except Exception:
            pass

        try:
            print ('%sOutside Temp:\t\t\t\t%.1f° %s| color=%s' % (prefix, convert_temp(temp_unit,climate_state['outside_temp']),temp_unit,color))
        except:
            print ('%sOutside Temp:\t\t\t\tUnavailable| color=%s' % (prefix, color))

        print ('%s---' % prefix)
        print ('%sVehicle info| color=%s' % (prefix,color))

        img_data = vehicle.compose_image(vehicle_config['car_type'],view=_CAR_DEFAULT_PICTURE_) 
        if not img_data == None:
            print ('%s--|image=%s href=%s color=%s' % (prefix, img_data, vehicle.compose_url(vehicle_config['car_type']), color))

        img_data = vehicle.compose_image(vehicle_config['car_type'],view=_CAR_DEFAULT_PICTURE_2_) 
        if not img_data == None:
            print ('%s--|image=%s alternate=true href=%s color=%s' % (prefix, img_data, vehicle.compose_url(vehicle_config['car_type']), color))
        
        # Top vehicle-info group (Name / VIN / Firmware). All rows in
        # the entire vehicle-info submenu — including Wheels and the
        # Model/Type/Color set below — share *the same* target column
        # so NSMenu's proportional-font tab stops line up the value
        # column across all of them. ``column_tabs`` returns a dict
        # mapping each prefixed-label to the right number of tabs.
        _hdr_prefix = prefix + '--'
        _all_labels = ['Name:', 'VIN:', 'Firmware:',
                       'Model:', 'Type:', 'Ludicrous:', 'Uncorked:',
                       'Color:', 'Roof:', 'Interior:', 'Wheels:']
        _hdr_tabs = column_tabs([_hdr_prefix + l for l in _all_labels])
        def _hdr_row(lbl, val):
            return '%s%s%s%s' % (_hdr_prefix, lbl, _hdr_tabs[_hdr_prefix + lbl], val)
        print ('%s-----' % prefix)
        print ('%s | color=%s' % (_hdr_row('Name:',     vehicle_name), color))
        print ('%s | terminal=true shell="echo %s | pbcopy" color=%s'
               % (_hdr_row('VIN:', vehicle_vin), vehicle_vin, color))
        print ('%s | terminal=true shell="echo %s | pbcopy" color=%s'
               % (_hdr_row('Firmware:', vehicle_state['car_version']),
                  vehicle_state['car_version'], color))
        
        # ``humanize_token`` rewrites enum-ish API values like ``modelx``
        # → ``Model X``, ``Turbine22Dark`` → ``Turbine 22 Dark`` so the
        # menu reads as prose instead of code. Trim badging ("p100d") is
        # a marketing string and is upper-cased verbatim.
        car_type = humanize_car_type(vehicle_config.get('car_type'))
        trim     = (vehicle_config.get('trim_badging') or '—').upper()
        print ('%s-----' % prefix)
        # Build a list of (label, value, color) rows for the
        # vehicle-info column, then render them aligned. ``None`` value
        # means "skip" so we can keep the conditionals readable.
        info_rows = [
            ('Model:',     car_type,                                                  info_color),
            ('Type:',      trim,                                                      info_color),
            ('Ludicrous:', 'Yes' if vehicle_config.get('has_ludicrous_mode') else None, info_color),
            ('Uncorked:',  humanize_token(vehicle_config['perf_config'])
                              if 'perf_config' in vehicle_config else None,           info_color),
            ('Color:',     humanize_token(vehicle_config.get('exterior_color', '—')), info_color),
            ('Roof:',      humanize_token(vehicle_config['roof_color'])
                              if vehicle_config.get('roof_color') and
                                 vehicle_config['roof_color'] != 'None' else None,    info_color),
            ('Interior:',  humanize_token(vehicle_config['interior_trim_type'])
                              if vehicle_config.get('interior_trim_type') else None,  info_color),
        ]
        info_rows = [r for r in info_rows if r[1] is not None]
        # Reuse ``_hdr_tabs`` so every row in the vehicle-info submenu
        # lands its value in the same NSMenu pixel tab-stop.
        for lbl, val, col in info_rows:
            print ('%s%s%s%s | color=%s'
                   % (_hdr_prefix, lbl, _hdr_tabs[_hdr_prefix + lbl], val, col))

        # Tire pressures: nested under "Wheels" submenu like before. We
        # also surface the recommended cold pressure (when present) so
        # the user can compare at a glance. Tab counts use the shared
        # info-column target so the value lands in the same column as
        # Model/Type/Color above.
        tirepressure = gui_settings['gui_tirepressure_units']
        rcp_front = vehicle_state.get('tpms_rcp_front_value')
        rcp_rear  = vehicle_state.get('tpms_rcp_rear_value')
        rcp_front_lbl = ('  (rec: %i %s)' % (convert_pressure(tirepressure, rcp_front), tirepressure)) if rcp_front else ''
        rcp_rear_lbl  = ('  (rec: %i %s)' % (convert_pressure(tirepressure, rcp_rear),  tirepressure)) if rcp_rear  else ''
        wheel_value = humanize_token(vehicle_config.get('wheel_type', '—'))
        print ('%s | color=%s' % (_hdr_row('Wheels:', wheel_value), info_color))
        # TPMS rows live one indent deeper (under the Wheels submenu).
        tpms_prefix = prefix + '----'
        tpms_labels = ('Front Left:', 'Front Right:', 'Rear Left:', 'Rear Right:')
        tpms_tabs   = column_tabs([tpms_prefix + l for l in tpms_labels])
        def _tpms_row(lbl, psi, rcp_label):
            value = '%i %s%s' % (convert_pressure(tirepressure, psi), tirepressure, rcp_label)
            return '%s%s%s%s' % (tpms_prefix, lbl, tpms_tabs[tpms_prefix + lbl], value)
        print ('%s | color=%s' % (_tpms_row('Front Left:',  vehicle_state['tpms_pressure_fl'], rcp_front_lbl), color))
        print ('%s | color=%s' % (_tpms_row('Front Right:', vehicle_state['tpms_pressure_fr'], rcp_front_lbl), color))
        print ('%s | color=%s' % (_tpms_row('Rear Left:',   vehicle_state['tpms_pressure_rl'], rcp_rear_lbl),  color))
        print ('%s | color=%s' % (_tpms_row('Rear Right:',  vehicle_state['tpms_pressure_rr'], rcp_rear_lbl),  color))

        # Vehicle configuration submenu — surfaces the rich data Tesla
        # gives us in ``vehicle_config`` (Autopilot version, drive units,
        # suspension, region, ...). Keeps "Vehicle info" tidy by hiding
        # the long list under one entry. ``humanize_token`` converts
        # CamelCase / snake_case enum values such as ``PermanentMagnet``
        # or ``FuturisFoldFlat`` into ``Permanent Magnet`` / ``Futuris
        # Fold Flat`` so they read like prose, not API codes.
        cfg_rows = []
        def _add(key, label, formatter=None):
            v = vehicle_config.get(key)
            if v is None or v == '' or v == 'None':
                return
            cfg_rows.append((label, formatter(v) if formatter else humanize_token(v)))
        _add('driver_assist',         'Autopilot:')
        _add('front_drive_unit',      'Front motor:')
        _add('rear_drive_unit',       'Rear motor:')
        _add('has_air_suspension',    'Air suspension:',  lambda v: 'Yes' if v else 'No')
        _add('has_seat_cooling',      'Seat cooling:',    lambda v: 'Yes' if v else 'No')
        _add('charge_port_type',      'Charge port:')
        _add('headlamp_type',         'Headlamps:')
        _add('spoiler_type',          'Spoiler:')
        _add('third_row_seats',       'Third row:')
        _add('rhd',                   'Right-hand drive:', lambda v: 'Yes' if v else 'No')
        _add('eu_vehicle',            'Region:',           lambda v: 'EU' if v else 'Non-EU')
        _add('efficiency_package',    'Efficiency pkg:')
        _add('plg',                   'Power liftgate:',   lambda v: 'Yes' if v else 'No')
        _add('motorized_charge_port', 'Motorized port:',   lambda v: 'Yes' if v else 'No')
        if cfg_rows:
            # Per-row tab counts so every value lands on the same
            # NSMenu pixel tab-stop regardless of label length.
            cfg_prefix = prefix + '----'
            cfg_tabs   = column_tabs([cfg_prefix + lbl for lbl, _ in cfg_rows])
            print ('%s--Configuration | color=%s' % (prefix, color))
            for label, value in cfg_rows:
                print ('%s%s%s%s | color=%s'
                       % (cfg_prefix, label, cfg_tabs[cfg_prefix + label],
                          value, info_color))

        # Option codes: Tesla's owner-API stopped returning real per-VIN
        # codes in 2019, so this menu is mostly a curiosity. Only render
        # it if we actually have *something* — empty / unknown rows are
        # noise. Users who want their real options can still set them
        # explicitly via Settings → Override option codes.
        codes_str = vehicle.option_codes() or ''
        codes = [c.strip() for c in codes_str.split(',') if c.strip()]
        if codes:
            print ('%s-----' % prefix)
            print ('%s--Options (%d) | color=%s' % (prefix, len(codes), color))
            print ('%s----Note: Tesla API may return incorrect codes | color=%s' % (prefix, color))
            print ('%s-------' % prefix)
            for option in codes:
                option_description = tesla_option_codes.get(option, 'Unknown')
                print ('%s----%s:\t\t%s | color=%s' % (prefix, option, option_description, info_color))

        print ('%s-----' % prefix)
        print ('%s--Images| color=%s' % (prefix , color))
        
        for view in _SHOW_CAR_PICTURES_:
            img_data = vehicle.compose_image(vehicle_config['car_type'],size=512,view=view,background='1')
            if not img_data == None:
                print ('%s----|image=%s href=%s color=%s' % (prefix, img_data, vehicle.compose_url(vehicle_config['car_type'],size=2048,view=view,background='1'), color))

            img_data = vehicle.compose_image(vehicle_config['car_type'],size=512,view=view,background='2')
            if not img_data == None:
                print ('%s----|image=%s alternate=true href=%s color=%s' % (prefix, img_data, vehicle.compose_url(vehicle_config['car_type'],size=2048,view=view,background='2'), color))


        # --------------------------------------------------
        # RECENT ALERTS MENU 
        # --------------------------------------------------

        # Tesla returns ``recent_alerts`` with a stable RFC-2822-ish time
        # string and a ``user_text`` field that occasionally is empty
        # (e.g. raised-suspension internal events). We:
        #   * skip rows whose user_text is empty so we don't render naked dashes
        #   * format the timestamp as ``YYYY-MM-DD HH:MM`` (local-time look,
        #     UTC offset preserved by the source)
        #   * use a single ``\t`` between timestamp and message so
        #     NSMenu's tab-stop alignment lines the message column up
        #     across rows. We deliberately *don't* try to split the
        #     message on ``/`` — Tesla's text contains real slashes
        #     ("I/O Error", "4MB/s+") and the heuristic picked the wrong
        #     one too often.
        alerts_iter = recent_alerts or []
        non_empty   = [a for a in alerts_iter if (a.get('user_text') or '').strip()]
        if non_empty:
            print ('%s--Alerts (%d) | color=%s' % (prefix, len(non_empty), color))
            for alert in non_empty:
                try:
                    ts = datetime.strptime(alert['time'], "%a, %d %b %Y %H:%M:%S %z")
                    ts_str = ts.strftime('%Y-%m-%d %H:%M')
                except Exception:
                    ts_str = alert.get('time', '')
                user_text = alert['user_text'].strip().replace('\n', ' ')
                print ('%s----%s\t%s | color=%s' % (prefix, ts_str, user_text, color))
        else:
            print ('%s--Alerts | color=%s' % (prefix, color))
            print ('%s----No recent alerts | color=%s' % (prefix, color))

        print ('%s-----' % prefix)
        print ('%s--Odometer: 		%s %s | color=%s' % (prefix, convert_distance(distance_unit,vehicle_state['odometer']), distance_unit, color))


        print ('%sVehicle commands| color=%s' % (prefix,color))
        print ('%s--Flash lights | refresh=true terminal=false shell="%s" param1=%s param2=flash_lights color=%s' % (prefix, cmd_path, str(i), color))
        print ('%s--Flash lights | refresh=true alternate=true terminal=true shell="%s" param1=%s param2=flash_lights color=%s' % (prefix, cmd_path, str(i), color))
        print ('%s--Honk horn | refresh=true terminal=false shell="%s" param1=%s param2=honk_horn color=%s' % (prefix, cmd_path, str(i), color))
        print ('%s--Honk horn | refresh=true alternate=true terminal=true shell="%s" param1=%s param2=honk_horn color=%s' % (prefix, cmd_path, str(i), color))
        print ('%s----- | color=%s' % (prefix,color))
        # Media: reflect *actual* playback status on the toggle so the
        # user can see at a glance whether music is currently coming
        # out of the speakers. Tesla's owner-API caches the last known
        # ``media_playback_status`` even when the car is asleep / parked
        # / unoccupied, which means a stale ``Playing`` badge would lie
        # about the current state. We treat the badge as authoritative
        # only when there's a driver in the seat — otherwise the music
        # is not actually audible and we drop the badge.
        media_info  = vehicle_state.get('media_info') or {}
        media_state = vehicle_state.get('media_state') or {}
        playback    = (media_info.get('media_playback_status') or '').strip()
        user_present = bool(vehicle_state.get('is_user_present'))
        is_playing  = (playback.lower() == 'playing') and user_present

        media_label = 'Media'
        if playback and user_present:
            media_label += ' (Playing)' if is_playing else ' (%s)' % playback
        print ('%s--%s| color=%s' % (prefix, media_label, color))

        toggle_lbl = 'Pause' if is_playing else 'Play'
        if not media_state.get('remote_control_enabled', True):
            toggle_lbl += ' (remote control disabled)'

        print ('%s----Now Playing | color=%s' % (prefix, color))
        print ('%s------%s | refresh=true terminal=false shell="%s" param1=%s param2=media_toggle_playback color=%s'
               % (prefix, toggle_lbl, cmd_path, str(i), color))
        print ('%s------%s | refresh=true alternate=true terminal=true shell="%s" param1=%s param2=media_toggle_playback color=%s'
               % (prefix, toggle_lbl, cmd_path, str(i), color))
        print ('%s-------' % prefix)
        try:
            station = media_info.get('now_playing_station') or ''
            print ('%s----Station:\t%s | color=%s' % (prefix, station or 'Unavailable', info_color))
        except Exception:
            print ('%s----Station:\tUnavailable | color=%s' % (prefix, info_color))
        try:
            title = media_info.get('now_playing_title') or ''
            print ('%s----Title: \t%s | color=%s' % (prefix, title or 'Unavailable', info_color))
        except Exception:
            print ('%s----Title: \tUnavailable | color=%s' % (prefix, info_color))
        try:
            artist = media_info.get('now_playing_artist') or ''
            print ('%s----Artist:\t%s | color=%s' % (prefix, artist or 'Unavailable', info_color))
        except Exception:
            print ('%s----Artist:\tUnavailable | color=%s' % (prefix, info_color))
        try:
            album = media_info.get('now_playing_album') or ''
            if album:
                print ('%s----Album: \t%s | color=%s' % (prefix, album, info_color))
        except Exception:
            pass
        try:
            source = media_info.get('now_playing_source') or ''
            if source:
                print ('%s----Source:\t%s | color=%s' % (prefix, source, info_color))
        except Exception:
            pass
        print ('%s-------' % prefix)
        print ('%s----Track| color=%s' % (prefix,color))
        print ('%s------Previous| refresh=true terminal=false shell="%s" param1=%s param2=media_prev_track color=%s' % (prefix, cmd_path, str(i), color))
        print ('%s------Previous| refresh=true alternate=true terminal=true shell="%s" param1=%s param2=media_prev_track color=%s' % (prefix, cmd_path, str(i), color))
        print ('%s------Next| refresh=true terminal=false shell="%s" param1=%s param2=media_next_track color=%s' % (prefix, cmd_path, str(i), color))
        print ('%s------Next| refresh=true alternate=true terminal=true shell="%s" param1=%s param2=media_next_track color=%s' % (prefix, cmd_path, str(i), color))
        print ('%s----Volume| color=%s' % (prefix,color))
        print ('%s------Current Volume: %s/%i | color=%s' % (prefix, int(vehicle_state['media_info']['audio_volume']), int(vehicle_state['media_info']['audio_volume_max']),color))
        print ('%s--------Up| refresh=true terminal=false shell="%s" param1=%s param2=media_volume_up color=%s' % (prefix, cmd_path, str(i), color))
        print ('%s--------Up| refresh=true alternate=true terminal=true shell="%s" param1=%s param2=media_volume_up color=%s' % (prefix, cmd_path, str(i), color))
        print ('%s--------Down| refresh=true terminal=false shell="%s" param1=%s param2=media_volume_down color=%s' % (prefix, cmd_path, str(i), color))
        print ('%s--------Down| refresh=true alternate=true terminal=true shell="%s" param1=%s param2=media_volume_down color=%s' % (prefix, cmd_path, str(i), color))
        print ('%s-----' % prefix)
        print ('%s--Navigate to address| refresh=true terminal=true shell="%s" param1=%s param2=navigation_request color=%s' % (prefix, cmd_path, str(i), color))
        
        
        if nearby_charging_sites:
            print ('%s--Navigate to nearby charger | color=%s' % (prefix, color))
            print ('%s----Tesla Superchargers | color=%s' % (prefix, color))
            for site, charger in enumerate(nearby_charging_sites['superchargers']): 
                if (charger == {} or not 'available_stalls' in charger):
                    continue
                print ('%s------%.2f %s \t(%s/%s)\t%s | refresh=true terminal=false shell="%s" param1=%s param2=navigation_set_charger param3=%s color=%s' % (prefix, convert_distance(distance_unit, charger['distance_miles']), distance_unit, charger['available_stalls'], charger['total_stalls'], charger['name'], cmd_path, i, location_encoder('Tesla Supercharger '+charger['name']), color))
                print ('%s------%.2f %s \t(%s/%s)\t%s | alternate=true refresh=true terminal=true shell="%s" param1=%s param2=navigation_set_charger param3=%s color=%s' % (prefix, convert_distance(distance_unit,charger['distance_miles']), distance_unit, charger['available_stalls'], charger['total_stalls'], charger['name'], cmd_path, i, location_encoder('Tesla Supercharger '+charger['name']), color))
            print ('%s----Destination Chargers | color=%s' % (prefix, color))
            for site, charger in enumerate(nearby_charging_sites['destination_charging']): 
                if (charger == {}):
                    continue
                print ('%s------%.2f %s \t%s\t | refresh=true terminal=false shell="%s" param1=%s param2=navigation_set_charger param3=%s color=%s' % (prefix, convert_distance(distance_unit,charger['distance_miles']), distance_unit, charger['name'], cmd_path, i, location_encoder(charger['name']), color))
                print ('%s------%.2f %s \t%s\t | alternate=true refresh=true terminal=true shell="%s" param1=%s param2=navigation_set_charger param3=%s color=%s' % (prefix, convert_distance(distance_unit,charger['distance_miles']), distance_unit, charger['name'], cmd_path, i, location_encoder(charger['name']), color))
        
        print ('%s-----' % prefix)

        # Homelink: show whether nearby + how many devices are paired.
        # Plain text — green is reserved for genuine alerts elsewhere.
        try:
            hl_nearby   = vehicle_state.get('homelink_nearby')
            hl_count    = vehicle_state.get('homelink_device_count')
            hl_label = 'Trigger Homelink'
            if hl_nearby:
                hl_label += ' (nearby'
                if hl_count:
                    hl_label += ', %d device%s' % (hl_count, '' if hl_count == 1 else 's')
                hl_label += ')'
            elif hl_count:
                hl_label += ' (%d configured)' % hl_count
        except Exception:
            hl_label = 'Trigger Homelink'

        print ('%s--%s | refresh=true terminal=false shell="%s" param1=%s param2=trigger_homelink param3=%s param4=%s color=%s' % (prefix, hl_label, cmd_path, str(i), 'lat:'+str(drive_state['latitude']),'lon:'+str(drive_state['longitude']), color))
        print ('%s--%s | refresh=true alternate=true terminal=true shell="%s" param1=%s param2=trigger_homelink param3=%s param4=%s color=%s' % (prefix, hl_label, cmd_path, str(i), 'lat:'+str(drive_state['latitude']),'lon:'+str(drive_state['longitude']), color))

        # Per-row tab counts so Dashcam / Valet mode / Speed limit
        # values all land in the same NSMenu pixel column.
        _cmd_prefix = prefix + '--'
        _cmd_tabs = column_tabs([_cmd_prefix + l for l in
                                 ('Dashcam:', 'Valet mode:', 'Speed limit:')])

        # Dashcam: show current state + Save Clip when capable.
        try:
            dc_state = vehicle_state.get('dashcam_state')
            if dc_state is not None:
                print ('%s--Dashcam:%s%s | color=%s'
                       % (prefix, _cmd_tabs[_cmd_prefix + 'Dashcam:'],
                          dashcam_label(dc_state), color))
                if vehicle_state.get('dashcam_clip_save_available'):
                    print ('%s----Save clip | refresh=true terminal=false shell="%s" param1=%s param2=dashcam_save_clip color=%s'
                           % (prefix, cmd_path, str(i), color))
                    print ('%s----Save clip | refresh=true alternate=true terminal=true shell="%s" param1=%s param2=dashcam_save_clip color=%s'
                           % (prefix, cmd_path, str(i), color))
        except Exception:
            pass

        # Valet mode: show current state + toggle hint.
        # We keep the red "(PIN required)" badge because that's a genuine
        # blocker — the user can't unlock the car without entering the PIN.
        try:
            valet = vehicle_state.get('valet_mode')
            if valet is not None:
                pin_warn = ''
                if vehicle_state.get('valet_pin_needed'):
                    pin_warn = ' ' + CRED + '(PIN required)' + CEND
                print ('%s--Valet mode:%s%s%s | color=%s'
                       % (prefix, _cmd_tabs[_cmd_prefix + 'Valet mode:'],
                          yes_no(valet), pin_warn, color))
                target = 'on:false' if valet else 'on:true'
                label  = 'Turn off' if valet else 'Turn on'
                # The valet command also accepts a numeric password via
                # ``password:1234`` — leave that to the user via Terminal.
                print ('%s----%s | refresh=true terminal=false shell="%s" param1=%s param2=set_valet_mode param3=%s color=%s'
                       % (prefix, label, cmd_path, str(i), target, color))
                print ('%s----%s | refresh=true alternate=true terminal=true shell="%s" param1=%s param2=set_valet_mode param3=%s color=%s'
                       % (prefix, label, cmd_path, str(i), target, color))
        except Exception:
            pass

        # Speed Limit Mode: show current state, and *only* expose the
        # toggle when the user has a PIN configured — without a PIN
        # there's nothing useful we can do here, and any "go set a PIN
        # in the Tesla app" message would just be a dead-end submenu.
        # We honour the user's distance preference when rendering the
        # current limit (Tesla always returns it in mph).
        try:
            slm = vehicle_state.get('speed_limit_mode') or {}
            if slm:
                active     = bool(slm.get('active'))
                cur_limit  = slm.get('current_limit_mph')
                pin_set    = slm.get('pin_code_set')
                if cur_limit:
                    if distance_unit == 'km':
                        limit_val  = int(round(float(cur_limit) * 1.609344))
                        limit_text = ' (%d km/h)' % limit_val
                    else:
                        limit_text = ' (%d mph)' % int(cur_limit)
                else:
                    limit_text = ''
                print ('%s--Speed limit:%s%s%s | color=%s'
                       % (prefix, _cmd_tabs[_cmd_prefix + 'Speed limit:'],
                          yes_no(active), limit_text, color))
                if pin_set:
                    target_cmd = 'speed_limit_deactivate' if active else 'speed_limit_activate'
                    target_lbl = 'Turn off' if active else 'Turn on'
                    print ('%s----%s (enter PIN in Terminal) | refresh=true terminal=true shell="%s" param1=%s param2=%s color=%s'
                           % (prefix, target_lbl, cmd_path, str(i), target_cmd, color))
        except Exception:
            pass

        print ('%s-----' % prefix)
        print ('%s--Remote start | refresh=true terminal=true shell="%s" param1=%s param2=remote_start_drive color=%s' % (prefix, cmd_path, str(i), color))


    # --------------------------------------------------
    # SETTINGS MENU (top-level — applies to all vehicles)
    # --------------------------------------------------
    print('---')
    print('Settings | color=%s' % color)
    print('--Update Google API keys | refresh=true terminal=true shell="%s" param1="keys" color=%s'
          % (cmd_path, color))
    print('--Override option codes | refresh=true terminal=true shell="%s" param1="overrides" color=%s'
          % (cmd_path, color))
    print('--Update Tesla option codes (from internet) | refresh=true terminal=true shell="%s" param1="update_codes" color=%s'
          % (cmd_path, color))
    print('--Toggle settings | refresh=true terminal=true shell="%s" param1="settings" color=%s'
          % (cmd_path, color))
    print('-----')
    # One-button re-auth: ``init`` already overwrites the stored
    # tokens on success and leaves them untouched on failure, so we
    # don't need a separate "Sign out" step. If the user really wants
    # to wipe their tokens without immediately signing back in, the
    # CLI ``param1="signout"`` entry point still exists and is invoked
    # from refresh-token failures elsewhere.
    print('--Sign in again | refresh=true terminal=true shell="%s" param1="init" color=%s'
          % (cmd_path, color))


if __name__ == '__main__':
    main(sys.argv)
