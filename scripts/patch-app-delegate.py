#!/usr/bin/env python3
"""Patch Capacitor AppDelegate.swift to route OAuth deep links back into the WebView."""

from __future__ import annotations

import sys
from pathlib import Path

MARKER = "handleStahapatiOAuthReturn"
VERSION_MARKER = "clearCancelledGoogleOAuthIfNeeded"
HELPER = r'''
    private func handleStahapatiOAuthReturn(_ url: URL) {
        guard url.scheme == "com.stahapatis.app" else { return }

        let queryItems = URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems ?? []
        if url.host == "auth-success" || url.host == "auth" {
            let hasError = queryItems.contains { item in
                let name = item.name.lowercased()
                guard ["error", "error_description", "error_code"].contains(name) else { return false }
                return !(item.value ?? "").trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            }
            let hasHttpError = queryItems.contains { item in
                guard ["status", "status_code", "http_status"].contains(item.name.lowercased()),
                      let value = item.value,
                      let status = Int(value) else { return false }
                return (400...599).contains(status)
            }
            let hasToken = queryItems.contains { item in
                item.name == "token" && !(item.value ?? "").trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            }

            guard !hasError, !hasHttpError, hasToken else {
                clearStahapatiWebSession()
                return
            }
        }

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

        guard let bridge = window?.rootViewController as? CAPBridgeViewController,
              let webView = bridge.webView else {
            NSLog("Unable to handle Sthapati OAuth return: Capacitor WebView is unavailable.")
            return
        }

        let loadCallback = {
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
                webView.load(URLRequest(url: targetURL))
            }
        }
        if url.host == "auth-success" || url.host == "auth" {
            webView.evaluateJavaScript("sessionStorage.removeItem('__stahapatiGoogleOAuthPending');") { _, error in
                if let error = error {
                    NSLog("Unable to clear pending Google OAuth marker: %@", error.localizedDescription)
                }
                loadCallback()
            }
        } else {
            loadCallback()
        }
    }

    private func clearStahapatiWebSession() {
        guard let bridge = window?.rootViewController as? CAPBridgeViewController,
              let webView = bridge.webView else {
            NSLog("Unable to clear failed Google signup session: Capacitor WebView is unavailable.")
            return
        }
        removeStahapatiAuthData(from: webView)
    }

    private func removeStahapatiAuthData(from webView: WKWebView) {
        guard let homeURL = URL(string: "https://sthapatiapp.com/") else {
            NSLog("Unable to reset failed Google signup session: invalid site URL.")
            return
        }

        let dataStore = webView.configuration.websiteDataStore
        let authDataTypes: Set<String> = [
            WKWebsiteDataTypeCookies,
            WKWebsiteDataTypeLocalStorage,
            WKWebsiteDataTypeSessionStorage,
            WKWebsiteDataTypeIndexedDBDatabases
        ]
        dataStore.fetchDataRecords(ofTypes: authDataTypes) { records in
            let siteRecords = records.filter { record in
                let displayName = record.displayName.lowercased()
                let host = URL(string: displayName.contains("://") ? displayName : "https://" + displayName)?.host?.lowercased() ?? displayName
                return host == "sthapatiapp.com" || host.hasSuffix(".sthapatiapp.com")
            }
            dataStore.removeData(ofTypes: authDataTypes, for: siteRecords) {
                DispatchQueue.main.async {
                    webView.load(URLRequest(url: homeURL))
                }
            }
        }
    }

    private func clearCancelledGoogleOAuthIfNeeded() {
        guard let bridge = window?.rootViewController as? CAPBridgeViewController,
              let webView = bridge.webView else { return }

        let script = "(function () { if (sessionStorage.getItem('__stahapatiGoogleOAuthPending') !== '1') return false; sessionStorage.removeItem('__stahapatiGoogleOAuthPending'); return true; })();"
        webView.evaluateJavaScript(script) { result, error in
            if let error = error {
                NSLog("Unable to inspect pending Google OAuth session: %@", error.localizedDescription)
                return
            }
            guard let wasPending = result as? Bool, wasPending else { return }
            self.removeStahapatiAuthData(from: webView)
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


def patch(path: Path) -> bool:
    content = path.read_text(encoding="utf-8")
    if VERSION_MARKER in content:
        return False

    if MARKER in content:
        helper_start = content.rfind("\n    private func handleStahapatiOAuthReturn")
        class_end = content.rfind("\n}\n")
        if helper_start == -1 or class_end < helper_start:
            raise SystemExit("Could not replace the existing OAuth callback helper.")
        content = content[:helper_start] + HELPER + content[class_end:]
    else:
        if OPEN_URL_OLD not in content:
            raise SystemExit(
                "AppDelegate.swift format changed; expected Capacitor open-url handler block."
            )
        content = content.replace(OPEN_URL_OLD, OPEN_URL_NEW)

    original_active_handler = (
        "    func applicationDidBecomeActive(_ application: UIApplication) {\n"
        "        // Restart any tasks that were paused (or not started) while the application was inactive. If the application was previously in the background, optionally refresh the user interface.\n"
        "    }"
    )
    if original_active_handler in content:
        content = content.replace(
            original_active_handler,
            "    func applicationDidBecomeActive(_ application: UIApplication) {\n"
            "        DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) { [weak self] in\n"
            "            self?.clearCancelledGoogleOAuthIfNeeded()\n"
            "        }\n"
            "    }",
        )
    elif "self?.clearCancelledGoogleOAuthIfNeeded()" not in content:
        raise SystemExit("Could not install OAuth cancellation handling.")

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
