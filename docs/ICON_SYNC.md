# Automatic device icon synchronization

GeloTech automatically prepares app icons when the existing ADB device monitor detects a single newly connected authorized device.

The detection path uses the existing ADB polling loop; no second device polling loop is created.

For a new serial, the app clears stale in-memory icon state and invokes the existing `action_sec_show_icons()` workflow in the background. That workflow installs `ApkIconHelper.apk` only when `com.drox.apkiconhelper` is missing, exports icons, pulls them into the local cache, and refreshes the Cleaner rows.

A serial is remembered for the current application session so the same device does not trigger a full export on every three-second ADB poll. A full disconnect clears the seen-serial state so a reconnect can prepare the device again.

Automatic sync currently waits when more than one authorized ADB device is connected because the existing helper/export command does not select a serial-specific target. Manual icon synchronization remains available through the existing action.
