[app]

title = ElectroPOS
package.name = electropos
package.domain = org.electropos

source.dir = .
source.include_exts = py,png,jpg,kv,atlas

version = 1.0.0

requirements = python3,kivy==2.3.0

orientation = portrait
fullscreen = 0

android.permissions = CAMERA
# Reduce to arm64-v8a only for a faster debug build
android.archs = arm64-v8a, armeabi-v7a
android.allow_backup = True

[buildozer]
log_level = 2
warn_on_root = 1