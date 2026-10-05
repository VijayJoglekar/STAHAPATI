#!/usr/bin/env python3
"""Patch Capacitor AppDelegate.swift to keep optional custom-scheme returns in the WebView.

Google signup itself stays inside the Capacitor WebView. This handler only exists so a
legacy com.stahapatis.app:// callback still loads the live site instead of being dropped.
"""

from __future__ import annotations

import sys
from pathlib import Path

MARKER = "handleStahapatiOAuthReturn"
VERSION_MARKER = "inAppGoogleOAuthNoSafariHandoff"
HELPER = r'''
    // inAppGoogleOAuthNoSafariHandoff
    private func handleStahapatiOAuthReturn(_ url: URL) {
        guard url.scheme == "com.stahapatis.app" else { return }

        var targetString = "https://sthapatiapp.com/"
        if let host = url.host, !host.isEmpty {
            if host == "auth-success" || host == "auth" {
                targetString = "https://sthapatiapp.com/auth"
                if let query = url.query, !query.isEmpty {
                    targetString += "?" + query
                }
            } else {
                targetString = "https://sthapatiapp.com/" + host
                if let query = url.query, !query.isEmpty {
                    targetString += "?" + query
                }
            }
        } else if let query = url.query, !query.isEmpty {
            targetString = "https://sthapatiapp.com/auth?" + query
        }

        guard let targetURL = URL(string: targetString) else { return }
        guard let bridge = window?.rootViewController as? CAPBridgeViewController,
              let webView = bridge.webView else {
            NSLog("Unable to handle Sthapati OAuth return: Capacitor WebView is unavailable.")
            return
        }

        DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
            webView.load(URLRequest(url: targetURL))
        }
    }
'''

OPEN_URL_OLD = """    func application(_ app: UIApplication, open url: URL, options: [UIApplication.OpenURLOptionsKey: Any] = [:]) -> Bool {
        // Called when the app was launched with a url. Feel free to add additional processing here,
        // but if you want the App API to support tracking app url opens, make sure to keep this call
        return ApplicationDelegateProxy.shared.application(app, open: url, options: options)
    }"""

OPEN_URL_NEW = """    func application(_ app: UIApplication, open url: URL, options: [UIApplication.OpenURLOptionsKey: Any] = [:]) -> Bool {
        handleStahapatiOAuthReturn(url)
        return ApplicationDelegateProxy.shared.application(app, open: url, options: options)
    }"""

BECOME_ACTIVE_OAUTH = """    func applicationDidBecomeActive(_ application: UIApplication) {
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) { [weak self] in
            self?.clearCancelledGoogleOAuthIfNeeded()
        }
    }"""

BECOME_ACTIVE_ORIGINAL = """    func applicationDidBecomeActive(_ application: UIApplication) {
        // Restart any tasks that were paused (or not started) while the application was inactive. If the application was previously in the background, optionally refresh the user interface.
    }"""


def strip_old_oauth_helpers(content: str) -> str:
    content = content.replace(BECOME_ACTIVE_OAUTH, BECOME_ACTIVE_ORIGINAL)

    helper_start = content.find("\n    private func handleStahapatiOAuthReturn")
    if helper_start == -1:
        return content

    class_end = content.find("\n}\n", helper_start)
    if class_end == -1:
        raise SystemExit("Could not remove the existing OAuth callback helper.")
    return content[:helper_start] + content[class_end:]


def patch(path: Path) -> bool:
    content = path.read_text(encoding="utf-8")
    if VERSION_MARKER in content:
        return False

    content = strip_old_oauth_helpers(content)

    if OPEN_URL_NEW not in content:
        if OPEN_URL_OLD not in content:
            raise SystemExit(
                "AppDelegate.swift format changed; expected Capacitor open-url handler block."
            )
        content = content.replace(OPEN_URL_OLD, OPEN_URL_NEW)

    if MARKER not in content:
        marker = "\n}\n"
        index = content.find(marker)
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
