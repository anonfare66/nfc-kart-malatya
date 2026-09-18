[app]
title = NFC Kart Malatya
package.name = nfckartmalatya
package.domain = com.burak
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,db
version = 1.0.0
requirements = python3,kivy==2.3.0,reportlab
orientation = landscape
fullscreen = 0
android.permissions = WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE
android.api = 33
android.minapi = 24
android.ndk = 25b
android.ndk_api = 24
android.archs = arm64-v8a
android.allow_backup = True
android.accept_sdk_license = True
android.debug_artifact = True

[buildozer]
log_level = 2
warn_on_root = 1
