[app]
title = منبّه الأذان
package.name = adhanalarm
package.domain = com.adhanalarm
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,ttf,ogg,wav
version = 0.1.1
requirements = python3,kivy,arabic-reshaper
orientation = portrait
fullscreen = 0
android.permissions = INTERNET,ACCESS_NETWORK_STATE
android.api = 35
android.minapi = 23
android.archs = arm64-v8a
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
