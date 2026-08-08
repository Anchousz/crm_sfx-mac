#!/bin/bash
set -e
cd "$(dirname "$0")"

PY=python3

$PY -m pip install --upgrade customtkinter openpyxl reportlab pillow pyinstaller

if [ -f assets/icon.png ]; then
    rm -rf build/icon.iconset
    mkdir -p build/icon.iconset
    for s in 16 32 64 128 256 512; do
        sips -z $s $s assets/icon.png --out "build/icon.iconset/icon_${s}x${s}.png" >/dev/null 2>&1 || true
    done
    cp "build/icon.iconset/icon_512x512.png" "build/icon.iconset/icon_256x256@2x.png" 2>/dev/null || true
    iconutil -c icns build/icon.iconset -o assets/icon.icns 2>/dev/null || true
fi

$PY -m PyInstaller --noconfirm --clean --windowed --name "SFX CRM" \
    --icon assets/icon.icns --collect-all customtkinter \
    --add-data "assets:assets" --osx-bundle-identifier ru.bisquare.sfxcrm \
    --target-architecture universal2 app.py

rm -rf build/dmg "installer/SFX-CRM-3.0.0.dmg"
mkdir -p build/dmg installer
cp -R "dist/SFX CRM.app" build/dmg/
ln -s /Applications build/dmg/Applications
hdiutil create -volname "SFX CRM" -srcfolder build/dmg -ov -format UDZO \
    "installer/SFX-CRM-3.0.0.dmg"

echo "Готово: installer/SFX-CRM-3.0.0.dmg (universal2)"
