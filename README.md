# Sthapati iOS App (Capacitor)

Wraps the live website **https://sthapatiapp.com** as a native iOS app for the App Store.

## What your Mac friend needs

1. Mac with macOS 13+
2. [Xcode](https://apps.apple.com/app/xcode/id497799835) (from App Store)
3. [Node.js 18+](https://nodejs.org/)
4. Apple Developer account ($99/year) — client must provide login access
5. Bundle ID registered in [Apple Developer Portal](https://developer.apple.com/account) (default: `com.stahapatis.app`)

## Quick start (Mac)

```bash
cd mobile
bash scripts/build-ios-app.sh
```

This will:
- Install npm dependencies
- Create the Capacitor iOS project
- Install CocoaPods
- Open Xcode

## Commands

| Command | Purpose |
|---------|---------|
| `bash scripts/build-ios-app.sh setup` | First-time setup only |
| `bash scripts/build-ios-app.sh open` | Open existing project in Xcode |
| `bash scripts/build-ios-app.sh archive` | Build `.xcarchive` + `.ipa` (CLI) |

## Upload to App Store (Xcode GUI — recommended first time)

1. Open Xcode → select **App** target
2. **Signing & Capabilities** → choose Team → enable **Automatically manage signing**
3. Connect iPhone → **Product → Run** to test
4. **Product → Archive**
5. **Distribute App → App Store Connect → Upload**

## CLI archive (optional)

```bash
export IOS_TEAM_ID="YOUR_TEAM_ID"   # from developer.apple.com/account
bash scripts/build-ios-app.sh archive
```

Output: `mobile/build/export/*.ipa`

## Customize

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_SITE_URL` | `https://sthapatiapp.com` | Live site URL loaded in the app |
| `IOS_BUNDLE_ID` | `com.stahapatis.app` | App Store bundle identifier |
| `APP_NAME` | `Sthapati` | App name on home screen |
| `APP_SCHEME` | `com.stahapatis.app` | OAuth deep link scheme |
| `IOS_TEAM_ID` | — | Required for CLI archive |

Example:

```bash
APP_SITE_URL=https://sthapatiapp.com IOS_BUNDLE_ID=com.stahapatis.app bash scripts/build-ios-app.sh setup
```

## App icons

Before App Store submission, replace icons in:

`ios/App/App/Assets.xcassets/AppIcon.appiconset/`

Use a 1024×1024 PNG of the Sthapati logo. The GitHub Actions workflow and `scripts/build-ios-app.sh setup` generate icons and splash assets automatically from `logo.png`.

## Google Sign-In (iOS)

Google signup/login stays **inside the app WebView**. It does not open Safari.

Expected flow:
1. App loads https://sthapatiapp.com in the Capacitor WebView.
2. Tap **Sign up with Google** / **Sign in with Google**.
3. Google OAuth runs in the same WebView (same cookie jar as the website).
4. Google returns to `https://sthapatiapp.com/api/auth/callback/google`.
5. The existing website session, OTP, and dashboard flow continue unchanged.

The iOS layer intercepts Capacitor's Safari handoff (`UIApplication.shared.open` on unknown hosts and on `window.open` / `target=_blank`). Google and Sthapati auth URLs, including `about:blank` OAuth popups, stay in the same WebView cookie jar so NextAuth can return to `https://sthapatiapp.com/api/auth/callback/google`. A `com.stahapatis.app://` URL is still accepted as a fallback and is loaded back into the WebView; it is not used as Google's OAuth redirect URI.

## Notes

- The app loads the **live website** — no need to rebuild when the website updates.
- Internet connection is required (unless you remove `server.url` and bundle the site locally).
- Add `mobile/node_modules/` and `mobile/ios/` to `.gitignore` if committing (ios folder can be regenerated with `setup`).
