#!/usr/bin/env python3
"""Install scroll/header fixes by extending AppDelegate and Main.storyboard."""

from __future__ import annotations

import sys
from pathlib import Path

MARKER = "StahapatiBridgeViewController"
SNIPPET_NAME = "bridge-viewcontroller.swift.snippet"


def ensure_imports(content: str) -> str:
    if "import WebKit" not in content:
        content = content.replace("import Capacitor\n", "import Capacitor\nimport WebKit\n")
    return content


def patch_app_delegate(app_delegate: Path, snippet: Path) -> None:
    content = app_delegate.read_text(encoding="utf-8")
    bridge_class = snippet.read_text(encoding="utf-8")
    content = ensure_imports(content)

    class_marker = f"class {MARKER}"
    if class_marker in content:
        start = content.find("\n" + class_marker)
        if start == -1:
            start = content.find(class_marker)
        if start != -1:
            content = content[:start].rstrip() + "\n" + bridge_class + "\n"
        else:
            content = content.rstrip() + "\n" + bridge_class + "\n"
    else:
        content = content.rstrip() + "\n" + bridge_class + "\n"

    app_delegate.write_text(content, encoding="utf-8")


def patch_storyboard(storyboard: Path) -> None:
    content = storyboard.read_text(encoding="utf-8")
    original = content

    content = content.replace(
        'customClass="CAPBridgeViewController"',
        f'customClass="{MARKER}"',
    )
    # The subclass is compiled into the App target, not the Capacitor module.
    # Leaving customModule="Capacitor" makes iOS fail to instantiate the WebView
    # host and shows a black screen after the launch screen.
    content = content.replace(
        f'customClass="{MARKER}" customModule="Capacitor"',
        f'customClass="{MARKER}" customModule="App" customModuleProvider="target"',
    )

    if f'customClass="{MARKER}"' not in content:
        raise SystemExit(
            "Main.storyboard format changed; expected CAPBridgeViewController custom class."
        )
    if f'customClass="{MARKER}" customModule="Capacitor"' in content:
        raise SystemExit(
            "Main.storyboard still points StahapatiBridgeViewController at the Capacitor module."
        )

    if content != original:
        storyboard.write_text(content, encoding="utf-8")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(f"Usage: {sys.argv[0]} <ios-app-dir>")

    ios_app_dir = Path(sys.argv[1])
    repo_root = Path(__file__).resolve().parents[1]
    snippet = repo_root / "scripts" / SNIPPET_NAME
    app_delegate = ios_app_dir / "AppDelegate.swift"
    storyboard = ios_app_dir / "Base.lproj" / "Main.storyboard"

    if not snippet.is_file():
        raise SystemExit(f"Missing snippet: {snippet}")
    if not app_delegate.is_file():
        raise SystemExit(f"AppDelegate not found: {app_delegate}")
    if not storyboard.is_file():
        raise SystemExit(f"Storyboard not found: {storyboard}")

    patch_app_delegate(app_delegate, snippet)
    patch_storyboard(storyboard)
    print("Applied iOS scroll/header fixes")


if __name__ == "__main__":
    main()
