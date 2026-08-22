#!/usr/bin/env node
/**
 * Apply the Sthapati iOS startup screen after `npx cap add ios`.
 * Replaces the Capacitor splash/logo launch screen with a plain "Loading..."
 * screen and copies the AppDelegate that hides it when the WebView is ready.
 */
const fs = require('fs');
const path = require('path');

const rootDir = path.resolve(__dirname, '..');
const iosAppDir = path.join(rootDir, 'ios', 'App', 'App');
const nativeDir = path.join(rootDir, 'native', 'ios');

function fail(message) {
  console.error(`[patch-ios-startup] ${message}`);
  process.exit(1);
}

function copyFile(from, to) {
  fs.copyFileSync(from, to);
  console.log(`[patch-ios-startup] wrote ${path.relative(rootDir, to)}`);
}

function writeWhiteSplashImages() {
  const splashDir = path.join(iosAppDir, 'Assets.xcassets', 'Splash.imageset');
  if (!fs.existsSync(splashDir)) {
    console.log('[patch-ios-startup] Splash.imageset not found; skipping image replace');
    return;
  }

  // 1x1 white PNG. Kept as a fallback if anything still references Splash.
  const whitePng = Buffer.from(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII=',
    'base64'
  );
  const splashFiles = fs.readdirSync(splashDir).filter((name) => name.toLowerCase().endsWith('.png'));
  if (splashFiles.length === 0) {
    fs.writeFileSync(path.join(splashDir, 'splash-white.png'), whitePng);
    return;
  }
  for (const file of splashFiles) {
    fs.writeFileSync(path.join(splashDir, file), whitePng);
  }
  console.log(`[patch-ios-startup] replaced ${splashFiles.length} splash image(s) with a blank white image`);
}

function main() {
  if (!fs.existsSync(iosAppDir)) {
    fail(`iOS app directory not found at ${iosAppDir}. Run cap add ios first.`);
  }

  const launchScreenSrc = path.join(nativeDir, 'LaunchScreen.storyboard');
  const appDelegateSrc = path.join(nativeDir, 'AppDelegate.swift');
  if (!fs.existsSync(launchScreenSrc) || !fs.existsSync(appDelegateSrc)) {
    fail(`Missing native iOS startup files in ${nativeDir}`);
  }

  copyFile(launchScreenSrc, path.join(iosAppDir, 'Base.lproj', 'LaunchScreen.storyboard'));
  copyFile(appDelegateSrc, path.join(iosAppDir, 'AppDelegate.swift'));
  writeWhiteSplashImages();

  const launchScreen = fs.readFileSync(path.join(iosAppDir, 'Base.lproj', 'LaunchScreen.storyboard'), 'utf8');
  if (!launchScreen.includes('Loading...')) {
    fail('LaunchScreen.storyboard does not contain Loading...');
  }
  if (launchScreen.includes('image="Splash"')) {
    fail('LaunchScreen.storyboard still references the Splash logo image');
  }

  console.log('[patch-ios-startup] iOS startup screen patched: Loading... (no logo)');
}

main();
