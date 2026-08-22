#!/usr/bin/env python3
"""Patch Capacitor AppDelegate.swift to route OAuth deep links back into the WebView."""

from __future__ import annotations

import sys
from pathlib import Path

MARKER = "handleStahapatiOAuthReturn"
HELPER = """
    private func handleStahapatiOAuthReturn(_ url: URL) {
        guard url.scheme == "com.stahapatis.app" else { return }

        var targetString = "https://sthapatiapp.com/auth"
        if let host = url.host, !host.isEmpty {
            if host == "auth-success" || host == "auth" {
                if let query = url.query, !query.isEmpty {
                    targetString = "https://sthapatiapp.com/auth?" + query
                }
            } else {
                targetString = "https://sthapatiapp.com/" + host
                if let query = url.query, !query.isEmpty {
                    targetString += "?" + query
                }
            }
        } else if let query = url.query, !query.isEmpty {
            targetString += "?" + query
        }

        guard let targetURL = URL(string: targetString) else { return }

        DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
            guard let bridge = self.window?.rootViewController as? CAPBridgeViewController else { return }
            bridge.webView?.load(URLRequest(url: targetURL))
        }
    }
"""

OPEN_URL_OLD = """    func application(_ app: UIApplication, open url: URL, options: [UIApplication.OpenURLOptionsKey: Any] = [:]) -> Bool {
        // Called when the app was launched with a url. Feel free to add additional processing here,
        // but if you want the App API to support tracking app url opens, make sure to keep this call
        return ApplicationDelegateProxy.shared.application(app, open: url, options: options)
    }"""

OPEN_URL_NEW = """    func application(_ app: UIApplication, open url: URL, options: [UIApplication.OpenURLOptionsKey: Any] = [:]) -> Bool {
        handleStahapatiOAuthReturn(url)
        return ApplicationDelegateProxy.shared.application(app, open: url, options: options)
    }"""


def patch(path: Path) -> bool:
    content = path.read_text(encoding="utf-8")
    if MARKER in content:
        return False

    if OPEN_URL_OLD not in content:
        raise SystemExit(
            "AppDelegate.swift format changed; expected Capacitor open-url handler block."
        )

    content = content.replace(OPEN_URL_OLD, OPEN_URL_NEW)

    marker = "\n}\n"
    index = content.rfind(marker)
    if index == -1:
        raise SystemExit("Could not find AppDelegate class closing brace.")

    content = content[:index] + HELPER + content[index:]
    path.write_text(content, encoding="utf-8")
    return True


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(f"Usage: {sys.argv[0]} <AppDelegate.swift>")

    delegate = Path(sys.argv[1])
    if not delegate.is_file():
        raise SystemExit(f"File not found: {delegate}")

    if patch(delegate):
        print(f"Patched {delegate}")
    else:
        print(f"Already patched: {delegate}")


if __name__ == "__main__":
    main()
