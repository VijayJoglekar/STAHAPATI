#!/usr/bin/env python3
"""Validate the iOS in-app Google OAuth navigation layer.

This does not hit Google or the live website. It checks that the Capacitor
wrapper will keep the existing NextAuth callback inside the WebView instead of
opening Safari.
"""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SNIPPET = ROOT / "scripts" / "bridge-viewcontroller.swift.snippet"
CONFIG = ROOT / "capacitor.config.json"
BUILD_SCRIPT = ROOT / "scripts" / "build-ios-app.sh"
APP_DELEGATE_PATCH = ROOT / "scripts" / "patch-app-delegate.py"


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def is_google_family_host(host: str) -> bool:
    host = host.lower()
    suffixes = [
        "google.com",
        "googleapis.com",
        "gstatic.com",
        "googleusercontent.com",
        "recaptcha.net",
        "g.co",
        "google.co.in",
        "google.co.uk",
        "youtube.com",
        "ytimg.com",
        "ggpht.com",
        "withgoogle.com",
        "googleadservices.com",
        "googletagmanager.com",
        "googlevideo.com",
    ]
    if any(host == suffix or host.endswith("." + suffix) for suffix in suffixes):
        return True
    parts = host.split(".")
    if len(parts) >= 3:
        country = ".".join(parts[-3:])
        if country.startswith("google.co.") or country.startswith("google.com."):
            return True
    return False


def capacitor_does_host(host: str, pattern: str) -> bool:
    """Mirror Capacitor 6 InstanceConfiguration.doesHost."""
    if pattern == "*":
        return True
    host_components = host.lower().split(".")
    pattern_components = pattern.lower().split(".")
    if len(host_components) != len(pattern_components):
        return False
    filtered_host = []
    filtered_pattern = []
    for host_part, pattern_part in zip(host_components, pattern_components):
        if pattern_part == "*":
            continue
        filtered_host.append(host_part)
        filtered_pattern.append(pattern_part)
    return filtered_host == filtered_pattern


def should_keep_in_app(url: str) -> bool:
    from urllib.parse import urlparse

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.hostname or "").lower()
    if host == "sthapatiapp.com" or host.endswith(".sthapatiapp.com"):
        return True
    return is_google_family_host(host)


def should_capture_popup(url: str | None) -> bool:
    if url is None or url == "":
        return True
    from urllib.parse import urlparse

    parsed = urlparse(url)
    if (parsed.scheme or "").lower() in {"", "about"}:
        return True
    return should_keep_in_app(url)


def main() -> None:
    snippet = SNIPPET.read_text(encoding="utf-8")
    config = CONFIG.read_text(encoding="utf-8")
    build_script = BUILD_SCRIPT.read_text(encoding="utf-8")
    app_delegate_patch = APP_DELEGATE_PATCH.read_text(encoding="utf-8")

    required_symbols = [
        "StahapatiInAppNavigationProxy",
        "shouldCapturePopup",
        "oauthPopupWebView",
        "createWebViewWith",
        "capacitorDidLoad",
        "navigationDelegate = proxy",
        "uiDelegate = proxy",
        "isGoogleFamilyHost",
        "sthapatiapp.com",
        "window.open",
        "/api/auth",
        "Safari/604.1",
    ]
    for symbol in required_symbols:
        if symbol not in snippet:
            fail(f"snippet is missing {symbol}")

    if "UIApplication.shared.open" in snippet:
        fail("snippet must not open URLs with UIApplication.shared.open")

    if "capacitorHandler?.webView(webView, createWebViewWith" not in snippet:
        fail("unrelated popups should still use Capacitor's createWebViewWith")

    if "inAppGoogleOAuthNoSafariHandoff" not in app_delegate_patch:
        fail("AppDelegate patch lost the in-app OAuth marker")

    for source_name, source in (("capacitor.config.json", config), ("build-ios-app.sh", build_script)):
        for host in ("accounts.google.com", "*.gstatic.com", "withgoogle.com", "Safari/604.1"):
            if host not in source:
                fail(f"{source_name} is missing {host}")

    keep = [
        "https://accounts.google.com/o/oauth2/v2/auth",
        "https://sthapatiapp.com/api/auth/callback/google",
        "https://www.sthapatiapp.com/auth/complete?intent=signup",
        "https://android.clients.google.com/auth",
        "https://accounts.youtube.com/accounts/SetSID",
        "https://ssl.gstatic.com/accounts",
        "https://accounts.google.co.in/",
        "https://myaccount.google.com/",
    ]
    for url in keep:
        if not should_keep_in_app(url):
            fail(f"should keep in app: {url}")

    leave = [
        "https://cdn.example.com/resume.pdf",
        "mailto:help@sthapatiapp.com",
        "https://github.com/sthapati",
    ]
    for url in leave:
        if should_keep_in_app(url):
            fail(f"should not force in-app: {url}")

    if not should_capture_popup(None):
        fail("nil popup URL must be captured")
    if not should_capture_popup("about:blank"):
        fail("about:blank popup must be captured")
    if not should_capture_popup("https://accounts.google.com/signup"):
        fail("Google signup popup must be captured")
    if should_capture_popup("https://cdn.example.com/resume.pdf"):
        fail("unrelated popups must still be allowed to leave the app")

    # Prove why suffix matching is required: Capacitor wildcards miss extra labels.
    if capacitor_does_host("android.clients.google.com", "*.google.com"):
        fail("test assumption failed: Capacitor should not match extra DNS labels")
    if not is_google_family_host("android.clients.google.com"):
        fail("suffix matcher must keep nested Google hosts in-app")

    callback = "https://sthapatiapp.com/api/auth/callback/google"
    if not should_keep_in_app(callback):
        fail("NextAuth Google callback must remain in the WebView cookie jar")

    print("in-app Google OAuth navigation checks passed")
    print("NextAuth callback stays in-app:", callback)


if __name__ == "__main__":
    main()
