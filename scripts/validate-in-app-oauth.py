#!/usr/bin/env python3
"""Check that the iOS wrapper leaves Google authentication to the system browser."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    config = json.loads((ROOT / "capacitor.config.json").read_text(encoding="utf-8"))
    allow_navigation = config.get("server", {}).get("allowNavigation", [])
    for pattern in allow_navigation:
        if "google" in pattern.lower() or "recaptcha" in pattern.lower():
            fail(f"Google authentication host is allowlisted in the WebView: {pattern}")

    if not any(host in {"sthapatiapp.com", "*.sthapatiapp.com"} for host in allow_navigation):
        fail("The live Sthapati website must remain available in the Capacitor WebView")

    build_script = (ROOT / "scripts" / "build-ios-app.sh").read_text(encoding="utf-8")
    snippet = (ROOT / "scripts" / "bridge-viewcontroller.swift.snippet").read_text(encoding="utf-8")
    bridge_patcher = (ROOT / "scripts" / "patch-bridge-viewcontroller.py").read_text(encoding="utf-8")

    forbidden = {
        "build-ios-app.sh": (
            build_script,
            ("google", "Safari/604.1", "GoogleAuth", "patch-app-delegate.py", "APP_SCHEME"),
        ),
        "bridge-viewcontroller.swift.snippet": (
            snippet,
            ("window.open", "createWebViewWith", "WKNavigationDelegate", "WKUIDelegate", "customUserAgent", "google.com"),
        ),
        "patch-bridge-viewcontroller.py": (
            bridge_patcher,
            ("OAuth", "navigation proxy", "Google"),
        ),
    }
    for source_name, (source, tokens) in forbidden.items():
        for token in tokens:
            if token.lower() in source.lower():
                fail(f"{source_name} still contains wrapper-level auth handling: {token}")

    if (ROOT / "scripts" / "patch-app-delegate.py").exists():
        fail("Legacy custom-scheme OAuth callback patch is still present")

    generated_config_path = ROOT / "ios" / "App" / "App" / "capacitor.config.json"
    if generated_config_path.is_file():
        generated_config = json.loads(generated_config_path.read_text(encoding="utf-8"))
        if generated_config.get("server", {}).get("allowNavigation") != allow_navigation:
            fail("Generated iOS Capacitor config does not match the authentication pass-through config")

    generated_delegate_path = ROOT / "ios" / "App" / "App" / "AppDelegate.swift"
    if generated_delegate_path.is_file():
        generated_delegate = generated_delegate_path.read_text(encoding="utf-8")
        for token in (
            "StahapatiInAppNavigationProxy",
            "handleStahapatiOAuthReturn",
            "clearCancelledGoogleOAuthIfNeeded",
            "customUserAgent",
        ):
            if token in generated_delegate:
                fail(f"Generated AppDelegate still contains legacy wrapper auth code: {token}")

    print("iOS authentication pass-through checks passed")


if __name__ == "__main__":
    main()
