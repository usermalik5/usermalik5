from pathlib import Path


def test_qt_modules_import_without_creating_a_window():
    import tech_qt_bootstrap
    tech_qt_bootstrap.enable_qt_mode()
    import tech_qt_icons
    import tech_qt_themes
    import tech_qt_mainwindow
    import tech_qt_app

    assert tech_qt_themes.DEFAULT_THEME in tech_qt_themes.PALETTES
    assert tech_qt_themes.DEFAULT_UI_FONT in tech_qt_themes.UI_FONTS
    assert callable(tech_qt_icons.load_icon)
    assert hasattr(tech_qt_mainwindow, "MainWindow")
    assert callable(tech_qt_app.main)


def test_qt_assets_have_tabler_and_dashboard_resources():
    root = Path(__file__).resolve().parents[1]
    tabler = root / "assets" / "icons" / "tabler" / "outline"
    dashboard = root / "assets" / "phone_devices" / "iPhone17_P_PM_CosmicOrange@2x.png"
    assert (tabler / "dashboard.svg").is_file()
    assert (tabler / "device-mobile.svg").is_file()
    assert dashboard.is_file()
