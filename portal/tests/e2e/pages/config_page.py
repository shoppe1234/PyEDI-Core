"""Config page object."""

from __future__ import annotations

from .base_page import BasePage


class ConfigPage(BasePage):
    def navigate(self) -> None:
        self.navigate_to("Config")
        self.wait_for_heading("Configuration")

    def has_config_json(self) -> bool:
        return self.page.locator("pre").is_visible()

    def get_config_text(self) -> str:
        return self.page.locator("pre").inner_text()
