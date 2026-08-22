#!/usr/bin/env bash
#
# Build the Sthapati iOS app on macOS (Capacitor wrapper for https://sthapatiapp.com)
#
# Run on Mac only. Requires Xcode + Apple Developer account for App Store upload.
#
# Usage:
#   bash scripts/build-ios-app.sh setup     # first-time setup
#   bash scripts/build-ios-app.sh open      # open Xcode project
#   bash scripts/build-ios-app.sh build     # build debug .app
#   bash scripts/build-ios-app.sh archive   # create .xcarchive (needs signing env vars)
#   bash scripts/build-ios-app.sh            # setup + open (default)
#
# Optional env vars for archive:
#   IOS_TEAM_ID=XXXXXXXXXX
#   IOS_BUNDLE_ID=com.stahapatis.app
#   IOS_SCHEME=App
#
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IOS_DIR="${ROOT_DIR}/ios"
APP_SITE_URL="${APP_SITE_URL:-https://sthapatiapp.com}"
APP_ID="${IOS_BUNDLE_ID:-com.stahapatis.app}"
APP_NAME="${APP_NAME:-Sthapati}"
APP_SCHEME="${APP_SCHEME:-com.stahapatis.app}"
IOS_SCHEME="${IOS_SCHEME:-App}"
ARCHIVE_PATH="${ROOT_DIR}/build/Stahapati.xcarchive"
EXPORT_PATH="${ROOT_DIR}/build/export"
ACTION="${1:-default}"

log() {
  printf '\n[%s] %s\n' "$(date +'%H:%M:%S')" "$*"
}

fail() {
  printf '\nERROR: %s\n' "$*" >&2
  exit 1
}

require_mac() {
  [[ "$(uname -s)" == "Darwin" ]] || fail "This script must run on macOS."
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "Missing required command: $1"
}

check_prerequisites() {
  require_mac
  require_cmd node
  require_cmd npm
  require_cmd git

  if ! xcodebuild -version >/dev/null 2>&1; then
    fail "Xcode is not installed. Install Xcode from the Mac App Store."
  fi

  if ! xcodebuild -showsdks 2>/dev/null | grep -q iphoneos; then
    fail "iOS SDK not found. Open Xcode once and install iOS platform components."
  fi

  if ! command -v pod >/dev/null 2>&1; then
    log "CocoaPods not found. Installing..."
    sudo gem install cocoapods
  fi

  node_major="$(node -p "process.versions.node.split('.')[0]")"
  if [[ "${node_major}" -lt 18 ]]; then
    fail "Node.js 18+ is required. Current: $(node -v)"
  fi
}

copy_web_assets() {
  local logo="${ROOT_DIR}/logo.png"
  local web_logo="${ROOT_DIR}/www/logo.png"

  [[ -f "${logo}" ]] || fail "logo.png not found in repository root."

  mkdir -p "${ROOT_DIR}/www"
  log "Copying logo into www/ for the in-app loader..."
  cp "${logo}" "${web_logo}"
  [[ -f "${web_logo}" ]] || fail "Failed to copy logo.png to www/logo.png"
}

write_capacitor_config() {
  local google_ios_client_id="${GOOGLE_IOS_CLIENT_ID:-YOUR_IOS_CLIENT_ID.apps.googleusercontent.com}"
  local google_server_client_id="${GOOGLE_SERVER_CLIENT_ID:-YOUR_SERVER_CLIENT_ID.apps.googleusercontent.com}"

  cat > "${ROOT_DIR}/capacitor.config.json" <<EOF
{
  "appId": "${APP_ID}",
  "appName": "${APP_NAME}",
  "webDir": "www",
  "server": {
    "url": "${APP_SITE_URL}",
    "cleartext": false,
    "errorPath": "index.html",
    "allowNavigation": [
      "sthapatiapp.com",
      "*.sthapatiapp.com",
      "accounts.google.com",
      "*.google.com",
      "google.com",
      "*.googleusercontent.com"
    ]
  },
  "ios": {
    "contentInset": "automatic",
    "allowsLinkPreview": false,
    "scrollEnabled": true,
    "limitsNavigationsToAppBoundDomains": false,
    "backgroundColor": "#ffffff"
  },
  "plugins": {
    "SplashScreen": {
      "launchShowDuration": 15000,
      "launchAutoHide": true,
      "backgroundColor": "#ffffff",
      "showSpinner": false
    },
    "StatusBar": {
      "style": "DARK",
      "backgroundColor": "#ffffff"
    },
    "GoogleAuth": {
      "iosClientId": "${google_ios_client_id}",
      "iosServerClientId": "${google_server_client_id}",
      "scopes": ["profile", "email"],
      "serverClientId": "${google_server_client_id}"
    },
    "CapacitorCookies": {
      "enabled": true
    }
  }
}
EOF
}

install_dependencies() {
  log "Installing npm dependencies..."
  cd "${ROOT_DIR}"
  if [[ -f package-lock.json ]]; then
    npm ci
  else
    npm install
  fi
}

add_ios_platform() {
  cd "${ROOT_DIR}"
  if [[ ! -d "${IOS_DIR}" ]]; then
    log "Adding iOS platform..."
    npx cap add ios
  else
    log "iOS platform already exists."
  fi
}

sync_ios() {
  log "Syncing Capacitor iOS project..."
  cd "${ROOT_DIR}"
  copy_web_assets
  write_capacitor_config
  npx cap sync ios

  if [[ -f "${IOS_DIR}/App/Podfile" ]]; then
    log "Installing CocoaPods..."
    cd "${IOS_DIR}/App"
    pod install
  fi
}

patch_startup_screen() {
  log "Patching iOS launch screen to Loading... (no logo)..."
  node "${ROOT_DIR}/scripts/patch-ios-startup.js"
}

setup_splash_assets() {
  local logo="${ROOT_DIR}/logo.png"
  local assets="${IOS_DIR}/App/App/Assets.xcassets"
  local splash="${assets}/Splash.imageset"

  [[ -f "${logo}" ]] || {
    log "logo.png not found; skipping splash replacement."
    return 0
  }
  [[ -d "${assets}" ]] || return 0

  log "Leaving splash images blank; launch screen uses Loading... text, not the logo."
  mkdir -p "${splash}"

  sips -z 2732 2732 "${logo}" --out "${splash}/splash-2732x2732.png" >/dev/null 2>&1 || \
    cp "${logo}" "${splash}/splash-2732x2732.png"
  sips -z 2732 2732 "${logo}" --out "${splash}/splash-2732x2732-1.png" >/dev/null 2>&1 || \
    cp "${logo}" "${splash}/splash-2732x2732-1.png"
  sips -z 2732 2732 "${logo}" --out "${splash}/splash-2732x2732-2.png" >/dev/null 2>&1 || \
    cp "${logo}" "${splash}/splash-2732x2732-2.png"

  cat > "${splash}/Contents.json" <<'EOF'
{
  "images": [
    {
      "idiom": "universal",
      "filename": "splash-2732x2732.png",
      "scale": "1x"
    },
    {
      "idiom": "universal",
      "filename": "splash-2732x2732-1.png",
      "scale": "2x"
    },
    {
      "idiom": "universal",
      "filename": "splash-2732x2732-2.png",
      "scale": "3x"
    }
  ],
  "info": {
    "version": 1,
    "author": "xcode"
  }
}
EOF
}

setup_app_icon_assets() {
  local logo="${ROOT_DIR}/logo.png"
  local assets="${IOS_DIR}/App/App/Assets.xcassets"
  local icon_set="${assets}/AppIcon.appiconset"

  [[ -f "${logo}" ]] || return 0
  [[ -d "${assets}" ]] || return 0

  log "Generating AppIcon assets from logo.png..."
  mkdir -p "${icon_set}"
  cp "${logo}" "${icon_set}/logo.png"
  cd "${icon_set}"

  sips -z 20 20 logo.png --out icon-20.png >/dev/null 2>&1 || true
  sips -z 40 40 logo.png --out icon-40.png >/dev/null 2>&1 || true
  sips -z 60 60 logo.png --out icon-60.png >/dev/null 2>&1 || true
  sips -z 29 29 logo.png --out icon-29.png >/dev/null 2>&1 || true
  sips -z 58 58 logo.png --out icon-58.png >/dev/null 2>&1 || true
  sips -z 87 87 logo.png --out icon-87.png >/dev/null 2>&1 || true
  sips -z 80 80 logo.png --out icon-80.png >/dev/null 2>&1 || true
  sips -z 120 120 logo.png --out icon-120.png >/dev/null 2>&1 || true
  sips -z 180 180 logo.png --out icon-180.png >/dev/null 2>&1 || true
  sips -z 76 76 logo.png --out icon-76.png >/dev/null 2>&1 || true
  sips -z 152 152 logo.png --out icon-152.png >/dev/null 2>&1 || true
  sips -z 167 167 logo.png --out icon-167.png >/dev/null 2>&1 || true
  sips -z 1024 1024 logo.png --out icon-1024.png >/dev/null 2>&1 || true

  cat > Contents.json <<'EOF'
{
  "images": [
    { "size": "20x20", "idiom": "iphone", "filename": "icon-20.png", "scale": "1x" },
    { "size": "20x20", "idiom": "iphone", "filename": "icon-40.png", "scale": "2x" },
    { "size": "20x20", "idiom": "iphone", "filename": "icon-60.png", "scale": "3x" },
    { "size": "29x29", "idiom": "iphone", "filename": "icon-29.png", "scale": "1x" },
    { "size": "29x29", "idiom": "iphone", "filename": "icon-58.png", "scale": "2x" },
    { "size": "29x29", "idiom": "iphone", "filename": "icon-87.png", "scale": "3x" },
    { "size": "40x40", "idiom": "iphone", "filename": "icon-40.png", "scale": "1x" },
    { "size": "40x40", "idiom": "iphone", "filename": "icon-80.png", "scale": "2x" },
    { "size": "40x40", "idiom": "iphone", "filename": "icon-120.png", "scale": "3x" },
    { "size": "60x60", "idiom": "iphone", "filename": "icon-60.png", "scale": "1x" },
    { "size": "60x60", "idiom": "iphone", "filename": "icon-120.png", "scale": "2x" },
    { "size": "60x60", "idiom": "iphone", "filename": "icon-180.png", "scale": "3x" },
    { "size": "76x76", "idiom": "ipad", "filename": "icon-76.png", "scale": "1x" },
    { "size": "76x76", "idiom": "ipad", "filename": "icon-152.png", "scale": "2x" },
    { "size": "83.5x83.5", "idiom": "ipad", "filename": "icon-167.png", "scale": "2x" },
    { "size": "1024x1024", "idiom": "ios-marketing", "filename": "icon-1024.png", "scale": "1x" }
  ],
  "info": { "version": 1, "author": "xcode" }
}
EOF

  cd "${ROOT_DIR}"
}

plist_set_or_add() {
  local plist="$1"
  local key="$2"
  local type="$3"
  local value="$4"

  /usr/libexec/PlistBuddy -c "Set :${key} ${value}" "${plist}" 2>/dev/null || \
    /usr/libexec/PlistBuddy -c "Add :${key} ${type} ${value}" "${plist}"
}

patch_info_plist() {
  local plist="${IOS_DIR}/App/App/Info.plist"
  [[ -f "${plist}" ]] || return 0

  log "Patching Info.plist (name, OAuth URL scheme, permissions)..."

  plist_set_or_add "${plist}" "CFBundleDisplayName" "string" "${APP_NAME}"
  plist_set_or_add "${plist}" "CFBundleName" "string" "${APP_NAME}"

  /usr/libexec/PlistBuddy -c "Delete :CFBundleURLTypes" "${plist}" 2>/dev/null || true
  /usr/libexec/PlistBuddy -c "Add :CFBundleURLTypes array" "${plist}"
  /usr/libexec/PlistBuddy -c "Add :CFBundleURLTypes:0 dict" "${plist}"
  /usr/libexec/PlistBuddy -c "Add :CFBundleURLTypes:0:CFBundleURLName string ${APP_SCHEME}" "${plist}"
  /usr/libexec/PlistBuddy -c "Add :CFBundleURLTypes:0:CFBundleURLSchemes array" "${plist}"
  /usr/libexec/PlistBuddy -c "Add :CFBundleURLTypes:0:CFBundleURLSchemes:0 string ${APP_SCHEME}" "${plist}"

  if [[ -n "${GOOGLE_IOS_CLIENT_ID:-}" ]]; then
    local reversed_client_id="com.googleusercontent.apps.${GOOGLE_IOS_CLIENT_ID%%.*}"
    /usr/libexec/PlistBuddy -c "Add :CFBundleURLTypes:1 dict" "${plist}"
    /usr/libexec/PlistBuddy -c "Add :CFBundleURLTypes:1:CFBundleURLName string Google" "${plist}"
    /usr/libexec/PlistBuddy -c "Add :CFBundleURLTypes:1:CFBundleURLSchemes array" "${plist}"
    /usr/libexec/PlistBuddy -c "Add :CFBundleURLTypes:1:CFBundleURLSchemes:0 string ${reversed_client_id}" "${plist}"
  fi

  plist_set_or_add "${plist}" "NSCameraUsageDescription" "string" "Sthapati needs camera access to upload profile and project photos."
  plist_set_or_add "${plist}" "NSPhotoLibraryUsageDescription" "string" "Sthapati needs photo library access to upload images."
  plist_set_or_add "${plist}" "NSPhotoLibraryAddUsageDescription" "string" "Sthapati needs permission to save photos."
}

patch_app_delegate() {
  local delegate="${IOS_DIR}/App/App/AppDelegate.swift"
  local patch_script="${ROOT_DIR}/scripts/patch-app-delegate.py"

  [[ -f "${delegate}" ]] || return 0
  [[ -f "${patch_script}" ]] || fail "Missing OAuth patch script: ${patch_script}"

  log "Patching AppDelegate for Google Sign-In return to app..."
  python3 "${patch_script}" "${delegate}"
}

patch_bridge_viewcontroller() {
  local ios_app_dir="${IOS_DIR}/App/App"
  local patch_script="${ROOT_DIR}/scripts/patch-bridge-viewcontroller.py"

  [[ -d "${ios_app_dir}" ]] || return 0
  [[ -f "${patch_script}" ]] || fail "Missing bridge patch script: ${patch_script}"

  log "Installing scroll/header fix for iOS WebView..."
  python3 "${patch_script}" "${ios_app_dir}"
}

open_xcode() {
  log "Opening Xcode..."
  cd "${ROOT_DIR}"
  npx cap open ios

  cat <<INSTRUCTIONS

Next steps in Xcode (for App Store):
  1. Select the "App" target → Signing & Capabilities
  2. Choose your Apple Developer Team
  3. Set Bundle Identifier (default: ${APP_ID})
  4. Product → Archive
  5. Distribute App → App Store Connect → Upload

Test on a real iPhone first:
  Product → Run (connect iPhone via USB, trust the device)

INSTRUCTIONS
}

build_ios() {
  local workspace="${IOS_DIR}/App/App.xcworkspace"
  local project="${IOS_DIR}/App/App.xcodeproj"
  local xcode_target=""

  if [[ -d "${workspace}" ]]; then
    xcode_target=(-workspace "${workspace}")
  elif [[ -d "${project}" ]]; then
    xcode_target=(-project "${project}")
  else
    fail "Xcode project not found. Run: bash scripts/build-ios-app.sh setup"
  fi

  mkdir -p "${ROOT_DIR}/build/DerivedData"

  log "Building iOS app (Debug)..."
  xcodebuild \
    "${xcode_target[@]}" \
    -scheme "${IOS_SCHEME}" \
    -configuration Debug \
    -sdk iphoneos \
    -derivedDataPath "${ROOT_DIR}/build/DerivedData" \
    CODE_SIGNING_ALLOWED=NO \
    CODE_SIGNING_REQUIRED=NO \
    build

  log "Build complete. App is in build/DerivedData/Build/Products/Debug-iphoneos/App.app"
}

archive_ios() {
  local workspace="${IOS_DIR}/App/App.xcworkspace"
  local project="${IOS_DIR}/App/App.xcodeproj"
  local xcode_target=""

  if [[ -d "${workspace}" ]]; then
    xcode_target=(-workspace "${workspace}")
  elif [[ -d "${project}" ]]; then
    xcode_target=(-project "${project}")
  else
    fail "Xcode project not found. Run: bash scripts/build-ios-app.sh setup"
  fi

  [[ -n "${IOS_TEAM_ID:-}" ]] || fail "Set IOS_TEAM_ID before archive. Example: export IOS_TEAM_ID=ABCDE12345"

  mkdir -p "${ROOT_DIR}/build"

  log "Creating iOS archive at ${ARCHIVE_PATH} ..."
  xcodebuild \
    "${xcode_target[@]}" \
    -scheme "${IOS_SCHEME}" \
    -configuration Release \
    -archivePath "${ARCHIVE_PATH}" \
    -destination "generic/platform=iOS" \
    DEVELOPMENT_TEAM="${IOS_TEAM_ID}" \
    CODE_SIGN_STYLE=Automatic \
    archive

  log "Exporting IPA to ${EXPORT_PATH} ..."
  cat > "${ROOT_DIR}/build/ExportOptions.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>method</key>
  <string>app-store-connect</string>
  <key>teamID</key>
  <string>${IOS_TEAM_ID}</string>
  <key>uploadSymbols</key>
  <true/>
  <key>signingStyle</key>
  <string>automatic</string>
</dict>
</plist>
EOF

  xcodebuild \
    -exportArchive \
    -archivePath "${ARCHIVE_PATH}" \
    -exportPath "${EXPORT_PATH}" \
    -exportOptionsPlist "${ROOT_DIR}/build/ExportOptions.plist"

  log "Done. IPA exported to: ${EXPORT_PATH}"
}

run_setup() {
  check_prerequisites
  copy_web_assets
  install_dependencies
  add_ios_platform
  sync_ios
  copy_web_assets
  setup_app_icon_assets
  patch_info_plist
  patch_startup_screen
  patch_app_delegate
  patch_bridge_viewcontroller
  log "Setup complete."
}

case "${ACTION}" in
  setup)
    run_setup
    ;;
  open)
    check_prerequisites
    open_xcode
    ;;
  build)
    check_prerequisites
    build_ios
    ;;
  archive)
    check_prerequisites
    archive_ios
    ;;
  default)
    run_setup
    open_xcode
    ;;
  *)
    fail "Unknown action: ${ACTION}. Use setup | open | build | archive"
    ;;
esac
