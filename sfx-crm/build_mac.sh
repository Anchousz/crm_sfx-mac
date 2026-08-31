#!/bin/bash
# Сборка SFX CRM под macOS: .app + .dmg
set -e
cd "$(dirname "$0")"

PY=python3

# Убедимся, что зависимости установлены
$PY -m pip install --upgrade customtkinter openpyxl reportlab pillow pyinstaller

# Генерируем .icns из assets/icon.png (если есть)
if [ -f assets/icon.png ]; then
    rm -rf build/icon.iconset
    mkdir -p build/icon.iconset
    for s in 16 32 64 128 256 512; do
        sips -z $s $s assets/icon.png --out "build/icon.iconset/icon_${s}x${s}.png" >/dev/null 2>&1 || true
    done
    cp "build/icon.iconset/icon_512x512.png" "build/icon.iconset/icon_256x256@2x.png" 2>/dev/null || true
    iconutil -c icns build/icon.iconset -o assets/icon.icns 2>/dev/null || true
fi

# Сборка .app
$PY -m PyInstaller --noconfirm --clean --windowed --name "SFX CRM" \
    --icon assets/icon.icns --collect-all customtkinter \
    --collect-all reportlab --collect-all openpyxl --collect-all PIL \
    --add-data "assets:assets" --osx-bundle-identifier ru.bisquare.sfxcrm app.py

# Создание .dmg
rm -rf build/dmg "installer/SFX-CRM-3.2.0.dmg"
mkdir -p build/dmg installer
cp -R "dist/SFX CRM.app" build/dmg/
ln -s /Applications build/dmg/Applications
hdiutil create -volname "SFX CRM" -srcfolder build/dmg -ov -format UDZO \
    "installer/SFX-CRM-3.2.0.dmg"

echo "Готово: installer/SFX-CRM-3.2.0.dmg"