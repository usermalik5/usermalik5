from pathlib import Path


def test_qt_modules_import_without_creating_a_window():
    import tech_qt_auto_refresh
    import tech_qt_backup
    import tech_qt_bezel
    import tech_qt_bootstrap
    import tech_qt_cleaner
    import tech_qt_compat
    import tech_qt_drivers
    import tech_qt_final_fixes
    import tech_qt_iconfix
    import tech_qt_icons
    import tech_qt_iconsync
    import tech_qt_mainwindow
    import tech_qt_mirror
    import tech_qt_phone
    import tech_qt_sidebar_compact
    import tech_qt_themes
    import tech_qt_ui
    import tech_qt_virustotal

    tech_qt_bootstrap.enable_qt_mode()

    import tech_qt_app

    assert tech_qt_themes.DEFAULT_THEME in tech_qt_themes.PALETTES
    assert tech_qt_themes.DEFAULT_UI_FONT in tech_qt_themes.UI_FONTS
    assert callable(tech_qt_icons.load_icon)
    assert hasattr(tech_qt_mainwindow, "MainWindow")
    assert callable(tech_qt_app.main)
    assert callable(tech_qt_auto_refresh.install_auto_refresh)
    assert callable(tech_qt_backup.install_backup_restore)
    assert callable(tech_qt_bezel.install_bezel_alias)
    assert callable(tech_qt_cleaner.install_cleaner_parity)
    assert callable(tech_qt_drivers.install_driver_workflow)
    assert callable(tech_qt_final_fixes.install_final_qt_fixes)
    assert callable(tech_qt_iconfix.install_icon_cache_lookup)
    assert callable(tech_qt_iconsync.install_icon_sync)
    assert callable(tech_qt_mirror.install_scrcpy)
    assert callable(tech_qt_phone.install_phone_frame)
    assert callable(tech_qt_sidebar_compact.install_sidebar_compact)
    assert callable(tech_qt_ui.install_visual_parity)
    assert callable(tech_qt_virustotal.install_virustotal)


def test_icon_sync_has_completion_signal_for_ui_refresh():
    from tech_qt_iconsync import _IconLogBridge

    assert hasattr(_IconLogBridge, "finished")


def test_qt_assets_have_tabler_and_dashboard_resources():
    root = Path(__file__).resolve().parents[1]
    tabler = root / "assets" / "icons" / "tabler" / "outline"
    dashboard = root / "assets" / "phone_devices" / "iPhone17_P_PM_CosmicOrange@2x.png"
    assert (tabler / "dashboard.svg").is_file()
    assert (tabler / "device-mobile.svg").is_file()
    assert dashboard.is_file()
