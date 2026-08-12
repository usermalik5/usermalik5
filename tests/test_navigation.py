from types import SimpleNamespace

from tech_navigation import NavigationController


class Frame:
    def __init__(self):
        self.visible = False

    def grid(self):
        self.visible = True

    def grid_remove(self):
        self.visible = False


class Button:
    def configure(self, **kwargs):
        self.kwargs = kwargs


def test_dashboard_is_default_and_unrestricted():
    app = SimpleNamespace(
        TAB_PERMS={"Cleaner": "cleaner"},
        _can=lambda perm: False,
        pages={"Dashboard": Frame()},
        page_nav_btns={"Dashboard": Button()},
        _page_factories={},
        _current_page=None,
        after=lambda *_args: None,
        _dash_refresh_if_visible=lambda: None,
    )
    nav = NavigationController(app)
    assert nav.show_after_login() is True
    assert app._current_page == "Dashboard"
    assert app.pages["Dashboard"].visible is True


def test_restricted_page_is_not_shown_without_permission():
    app = SimpleNamespace(
        TAB_PERMS={"Cleaner": "cleaner"},
        _can=lambda perm: False,
        pages={"Dashboard": Frame(), "Cleaner": Frame()},
        page_nav_btns={"Dashboard": Button(), "Cleaner": Button()},
        _page_factories={},
        _current_page="Dashboard",
        after=lambda *_args: None,
        _dash_refresh_if_visible=lambda: None,
    )
    nav = NavigationController(app)
    assert nav.show("Cleaner") is False
    assert app._current_page == "Dashboard"
