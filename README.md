# ElectroPOS

Electronics retail app: manage inventory and sell products by barcode.
One Python/Kivy codebase that builds to **Android (.apk)** and **Windows (.exe)**.

## Features

- **Sell screen (POS):** scan/type a barcode -> item added to cart, adjust quantities, checkout with automatic stock reduction and receipt.
- **Inventory:** add / edit / delete products (barcode, name, category, cost, sell price, stock), live search, CSV export.
- **Sales history:** every sale with date, items and total; view receipt details; CSV export.
- **Barcode scanning:** any USB or Bluetooth barcode scanner works out of the box (it types the code + Enter). Manual entry always works. Optional camera scanning on Android (see below).
- **Offline:** all data is stored locally in a SQLite database.

On first launch a sample product is created: barcode `1234567890123` (HDMI Cable) so you can test the sell flow immediately.

## Run on your PC (no build needed)

```
pip install kivy==2.3.0
python main.py
```

or double-click `run.bat` on Windows.

## Get the Android APK and Windows EXE

### Option A - GitHub Actions (easiest, nothing to install)

1. Create a free GitHub account and a new repository.
2. Upload all files from this folder to the repository (via "uploading an existing file" or git).
3. Open the **Actions** tab -> select **Build APK and EXE** -> **Run workflow**.
4. Wait (APK job: ~20-40 min the first time; EXE job: ~5 min).
5. Download the artifacts: `ElectroPOS.apk` (install on Android) and `ElectroPOS.exe` (run on Windows).

Every push to the repository rebuilds both automatically.

### Option B - Build the APK yourself (Ubuntu or WSL)

```
pip install --upgrade buildozer "cython<3"
sudo apt install git zip unzip openjdk-17-jdk autoconf libtool pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev libtinfo5 cmake libffi-dev libssl-dev
buildozer android debug     # result: bin/electropos-1.0.0-arm64-v8a-debug.apk
```

First build downloads the Android SDK/NDK (~10 GB) and takes 20-40 minutes.

### Option C - Build the EXE yourself (Windows PC)

Double-click `build_exe.bat`. Result: `dist\ElectroPOS.exe`.

## Using a barcode scanner

- **USB / Bluetooth scanner:** just plug it in (or pair). It works like a keyboard: it types the barcode into the sell screen and presses Enter. No setup needed. This is the recommended way on the desktop and on Android (USB OTG or Bluetooth scanners).
- **Phone camera (optional):** install the zbarcam extension to enable the in-app Scan button:
  - Desktop: `pip install "kivy-garden.zbarcam[opencv]"` then `garden install zbarcam` (older Kivy) - the app auto-detects it.
  - Android: add `zbarcam` to `garden_requirements` and `opencv,pyzbar` to `requirements` in `buildozer.spec` (see kivy-garden/zbarcam docs).

## Data & backup

- Database: `electropos.db` (SQLite) - in the app user-data folder:
  - Windows: `C:\Users\<you>\AppData\Roaming\electropos\` (or `~/.electropos` when run from source)
  - Android: app private storage (uninstalling the app deletes it)
- CSV exports (`inventory.csv`, `sales.csv`) are saved next to the database.

## Project layout

```
main.py      - Kivy UI (POS, inventory, product form, sales, optional scanner)
db.py        - SQLite data layer (products, sales, stock, CSV export)
buildozer.spec            - Android build config
build_exe.bat             - Windows one-click EXE build
run.bat                   - quick desktop run
.github/workflows/build.yml - cloud builds for APK + EXE
```