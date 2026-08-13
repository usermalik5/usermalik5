from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / 'tech_secops4.py'
text = path.read_text(encoding='utf-8')
start = text.index('    def action_sec_show_icons(self):')
end = text.index('    def action_sec_backup_restore(self):', start)

new_method = r'''    def _icon_device_key(self, serial):
        return hashlib.sha256(serial.encode("utf-8", "replace")).hexdigest()[:32]

    def _icon_device_cache_dir(self, serial):
        path = os.path.join(get_settings_dir(), "icon_cache", self._icon_device_key(serial))
        os.makedirs(path, exist_ok=True)
        return path

    def _icon_cache_meta_path(self, serial):
        return os.path.join(self._icon_device_cache_dir(serial), "sync.json")

    def _icon_load_meta(self, serial):
        try:
            with open(self._icon_cache_meta_path(serial), "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError, TypeError):
            return {}

    def _icon_save_meta(self, serial, meta):
        path = self._icon_cache_meta_path(serial)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, sort_keys=True)
        os.replace(tmp, path)

    def _icon_run_cmd(self, args, timeout=15):
        return subprocess.run([self.scrcpy_adb] + args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)

    def _icon_wait_for_helper(self, attempts=4, delay=1.0):
        """Verify helper presence; package-manager transients are not treated as missing."""
        import time
        last_error = ""
        for attempt in range(attempts):
            result = self._icon_run_cmd(["shell", "pm", "path", "com.drox.apkiconhelper"])
            out = (result.stdout or "").strip()
            err = (result.stderr or "").strip()
            if "package:" in out:
                return out.split("package:", 1)[1].splitlines()[0].strip(), None
            last_error = out or err
            transient = any(token in (out + " " + err).lower() for token in ("can't find service", "package manager", "binder", "service"))
            if attempt < attempts - 1 and (transient or not out):
                time.sleep(delay)
                continue
            if attempt < attempts - 1:
                time.sleep(delay)
        return None, last_error

    def _icon_package_fingerprint(self):
        result = self._icon_run_cmd(["shell", "pm", "list", "packages"], 30)
        packages = sorted(
            line.split(":", 1)[1].strip()
            for line in (result.stdout or "").splitlines()
            if line.strip().startswith("package:") and line.split(":", 1)[1].strip()
        )
        if not packages:
            return None, 0
        return hashlib.sha256("\n".join(packages).encode("utf-8")).hexdigest(), len(packages)

    def _icon_restore_device_cache(self, serial):
        cache_dir = self._icon_device_cache_dir(serial)
        meta = self._icon_load_meta(serial)
        manifest = os.path.join(cache_dir, "packages.jsonl")
        if not meta.get("package_fingerprint") or not os.path.isfile(manifest):
            return False
        local = get_cache_dir()
        os.makedirs(local, exist_ok=True)
        copied = 0
        for name in os.listdir(cache_dir):
            if not name.endswith(".png"):
                continue
            try:
                shutil.copy2(os.path.join(cache_dir, name), os.path.join(local, name))
                copied += 1
            except OSError:
                pass
        return copied > 0

    def _icon_store_device_cache(self, serial, manifest, package_fingerprint, package_count):
        cache_dir = self._icon_device_cache_dir(serial)
        local = os.path.dirname(manifest)
        shutil.copy2(manifest, os.path.join(cache_dir, "packages.jsonl"))
        icon_count = 0
        for name in os.listdir(local):
            if not name.endswith(".png"):
                continue
            try:
                shutil.copy2(os.path.join(local, name), os.path.join(cache_dir, name))
                icon_count += 1
            except OSError:
                pass
        self._icon_save_meta(serial, {
            "serial": serial,
            "package_fingerprint": package_fingerprint,
            "package_count": package_count,
            "icon_count": icon_count,
            "helper_verified": True,
            "synced_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        })

    def action_sec_show_icons(self, automatic=False, force=False):
        def worker():
            import time
            serial = None
            try:
                state = ""
                for _ in range(4):
                    state = self._icon_run_cmd(["get-state"]).stdout.strip().lower()
                    if state == "device":
                        break
                    if state == "unauthorized":
                        self.after(0, lambda: self._sec_log("[GeloTech] Icons: authorize USB debugging on the phone first.", "#e74c3c"))
                        return
                    time.sleep(1.0)
                if state != "device":
                    self.after(0, lambda: self._sec_log("[GeloTech] Icons: device is not ready yet; automatic sync will wait for the next device event.", "#f39c12"))
                    return

                serial_result = self._icon_run_cmd(["get-serialno"])
                serial = (serial_result.stdout or "").strip()
                if not serial or serial.lower() in {"unknown", "no permissions"}:
                    self.after(0, lambda: self._sec_log("[GeloTech] Icons: could not identify the connected device.", "#e74c3c"))
                    return

                fingerprint, package_count = self._icon_package_fingerprint()
                if fingerprint is None:
                    self.after(0, lambda: self._sec_log("[GeloTech] Icons: package list is not ready; automatic sync skipped for now.", "#f39c12"))
                    return

                meta = self._icon_load_meta(serial)
                cache_matches = meta.get("package_fingerprint") == fingerprint and bool(meta.get("icon_count"))
                if cache_matches and not force and self._icon_restore_device_cache(serial):
                    self._sec_icon_cache = {}
                    self._sec_tree_icon_cache = {}
                    self._app_labels = None
                    self.after(0, self._sec_render_rows)
                    self.after(0, lambda: self._sec_log(f"[GeloTech] Icons ready from device cache ({meta.get('icon_count', 0)} icons).", "#2ecc71"))
                    return

                helper_path, helper_error = self._icon_wait_for_helper()
                if not helper_path:
                    transient = helper_error and any(token in helper_error.lower() for token in ("can't find service", "package manager", "binder", "service"))
                    if transient:
                        self.after(0, lambda: self._sec_log("[GeloTech] Android package manager is still starting; no APK was pushed.", "#f39c12"))
                        return
                    helper = os.path.join(get_bundle_dir(), "ApkIconHelper.apk")
                    if not os.path.isfile(helper):
                        self.after(0, lambda: self._sec_log("[GeloTech] Missing ApkIconHelper.apk in the application bundle.", "#e74c3c"))
                        return
                    self.after(0, lambda: self._sec_log("[GeloTech] ApkIconHelper not found; installing it once...", "#58a6ff"))
                    install = self._icon_run_cmd(["install", "-r", "-t", helper], 60)
                    combined = (install.stdout or "") + (install.stderr or "")
                    if "Success" not in combined:
                        msg = combined.strip()[-300:]
                        self.after(0, lambda m=msg: self._sec_log(f"[GeloTech] Helper install failed: {m}", "#e74c3c"))
                        return
                    helper_path, _ = self._icon_wait_for_helper()
                    if not helper_path:
                        self.after(0, lambda: self._sec_log("[GeloTech] Helper installed but verification failed; automatic sync stopped without another install attempt.", "#e74c3c"))
                        return

                meta["helper_verified"] = True
                meta["helper_verified_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                self._icon_save_meta(serial, meta)

                if not force and cache_matches and self._icon_restore_device_cache(serial):
                    self._sec_icon_cache = {}
                    self._sec_tree_icon_cache = {}
                    self._app_labels = None
                    self.after(0, self._sec_render_rows)
                    self.after(0, lambda: self._sec_log(f"[GeloTech] Icons restored from cache ({meta.get('icon_count', 0)} icons).", "#2ecc71"))
                    return

                export = "/sdcard/Android/data/com.drox.apkiconhelper/files/apk_icon_export"
                flag = export + "/DONE.flag"
                self._icon_run_cmd(["shell", "rm", "-f", flag])
                self._icon_run_cmd(["shell", "svc", "power", "stayon", "true"])
                self._icon_run_cmd(["shell", "input", "keyevent", "KEYCODE_WAKEUP"])
                self._icon_run_cmd(["shell", "wm", "dismiss-keyguard"])

                def launch():
                    self._icon_run_cmd(["shell", "am", "start", "-n", "com.drox.apkiconhelper/.MainActivity", "--ez", "autoExport", "true"])

                def done_flag():
                    return bool((self._icon_run_cmd(["shell", "cat", flag]).stdout or "").strip())

                completed = False
                for attempt in range(2):
                    launch()
                    for _ in range(60):
                        time.sleep(2)
                        if done_flag():
                            completed = True
                            break
                    if completed:
                        break
                    self.after(0, lambda: self._sec_log("[GeloTech] Icon export timed out; retrying once...", "#f39c12"))
                    self._icon_run_cmd(["shell", "am", "force-stop", "com.drox.apkiconhelper"])
                    time.sleep(2)

                self._icon_run_cmd(["shell", "svc", "power", "stayon", "false"])
                if not completed:
                    self.after(0, lambda: self._sec_log("[GeloTech] Icon export did not finish. Automatic retry waits for another device event.", "#e74c3c"))
                    return

                local = get_cache_dir()
                os.makedirs(local, exist_ok=True)
                self._icon_run_cmd(["pull", export, local], 120)
                manifest = os.path.join(local, "packages.jsonl")
                if not os.path.isfile(manifest):
                    manifest = os.path.join(local, "apk_icon_export", "packages.jsonl")

                count = 0
                if os.path.isfile(manifest):
                    with open(manifest, "r", encoding="utf-8") as f:
                        for line in f:
                            try:
                                item = json.loads(line)
                                pkg = item.get("package", "")
                                icon = item.get("icon", "")
                                if pkg and icon:
                                    src = os.path.join(os.path.dirname(manifest), icon)
                                    if os.path.isfile(src):
                                        shutil.copy2(src, os.path.join(local, f"{pkg}.png"))
                                        count += 1
                            except Exception:
                                continue

                self._icon_store_device_cache(serial, manifest, fingerprint, package_count)
                self._icon_run_cmd(["shell", "am", "force-stop", "com.drox.apkiconhelper"])
                self._sec_icon_cache = {}
                self._sec_tree_icon_cache = {}
                self._app_labels = None
                self.after(0, self._sec_render_rows)
                self.after(0, lambda: self._sec_log(f"[GeloTech] Icons synced: {count} apps; device cache updated.", "#2ecc71"))
            except Exception as exc:
                if serial:
                    try:
                        meta = self._icon_load_meta(serial)
                        meta["last_error"] = str(exc)
                        self._icon_save_meta(serial, meta)
                    except Exception:
                        pass
                self.after(0, lambda e=exc: self._sec_log(f"[GeloTech] Icon sync error: {e}", "#e74c3c"))
        threading.Thread(target=worker, daemon=True).start()

'''

path.write_text(text[:start] + new_method + text[end:], encoding='utf-8')
print('Icon cache migration applied.')
