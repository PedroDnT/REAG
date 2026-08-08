#!/usr/bin/env python
"""Playwright workflow automation script.

Este script automatiza um fluxo de navegador com etapas configuráveis via
variáveis de ambiente. Ajuste os seletores e URLs conforme o fluxo desejado.
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Callable

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class WorkflowConfig:
  base_url: str
  headless: bool
  username: str | None
  password: str | None
  username_selector: str | None
  password_selector: str | None
  submit_selector: str | None
  post_login_selector: str | None
  navigation_selector: str | None
  navigation_wait_selector: str | None
  screenshot_path: Path | None


def configure_logging() -> None:
  logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
  )


def load_config() -> WorkflowConfig:
  base_url = os.getenv("WORKFLOW_BASE_URL")
  if not base_url:
    raise ValueError("WORKFLOW_BASE_URL não definido.")

  headless_raw = os.getenv("WORKFLOW_HEADLESS", "true").lower().strip()
  headless = headless_raw not in {"0", "false", "no"}

  screenshot_env = os.getenv("WORKFLOW_SCREENSHOT_PATH")
  screenshot_path = Path(screenshot_env) if screenshot_env else None

  return WorkflowConfig(
    base_url=base_url,
    headless=headless,
    username=os.getenv("WORKFLOW_USERNAME"),
    password=os.getenv("WORKFLOW_PASSWORD"),
    username_selector=os.getenv("WORKFLOW_USERNAME_SELECTOR"),
    password_selector=os.getenv("WORKFLOW_PASSWORD_SELECTOR"),
    submit_selector=os.getenv("WORKFLOW_SUBMIT_SELECTOR"),
    post_login_selector=os.getenv("WORKFLOW_POST_LOGIN_SELECTOR"),
    navigation_selector=os.getenv("WORKFLOW_NAV_SELECTOR"),
    navigation_wait_selector=os.getenv("WORKFLOW_NAV_WAIT_SELECTOR"),
    screenshot_path=screenshot_path,
  )


def retry(action: Callable[[], None], label: str, attempts: int = 3, delay_s: float = 1.5) -> None:
  last_error: Exception | None = None
  for attempt in range(1, attempts + 1):
    try:
      LOGGER.info("%s (tentativa %s/%s)", label, attempt, attempts)
      action()
      return
    except Exception as exc:  # noqa: BLE001 - erro é relançado após retries
      last_error = exc
      LOGGER.warning("Falha em %s: %s", label, exc)
      if attempt < attempts:
        time.sleep(delay_s)
  if last_error:
    raise last_error


def maybe_fill(page, selector: str | None, value: str | None, label: str) -> None:
  if not selector or not value:
    LOGGER.info("%s não configurado; pulando.", label)
    return
  page.wait_for_selector(selector, state="visible", timeout=15_000)
  page.fill(selector, value)


def maybe_click(page, selector: str | None, label: str) -> None:
  if not selector:
    LOGGER.info("%s não configurado; pulando.", label)
    return
  page.wait_for_selector(selector, state="visible", timeout=15_000)
  page.click(selector)


def run_workflow(config: WorkflowConfig) -> None:
  with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=config.headless)
    context = browser.new_context()
    page = context.new_page()

    retry(lambda: page.goto(config.base_url, wait_until="networkidle"), "Abrir URL")

    try:
      maybe_fill(page, config.username_selector, config.username, "Usuário")
      maybe_fill(page, config.password_selector, config.password, "Senha")
      maybe_click(page, config.submit_selector, "Login")

      if config.post_login_selector:
        page.wait_for_selector(config.post_login_selector, state="visible", timeout=20_000)
        LOGGER.info("Login confirmado via selector pós-login.")

      maybe_click(page, config.navigation_selector, "Navegação")
      if config.navigation_wait_selector:
        page.wait_for_selector(config.navigation_wait_selector, state="visible", timeout=20_000)
        LOGGER.info("Navegação concluída.")

      if config.screenshot_path:
        config.screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(config.screenshot_path), full_page=True)
        LOGGER.info("Screenshot salvo em %s", config.screenshot_path)
    except PlaywrightTimeoutError as exc:
      LOGGER.error("Timeout no fluxo: %s", exc)
      raise
    finally:
      context.close()
      browser.close()


def main() -> None:
  configure_logging()
  config = load_config()
  run_workflow(config)


if __name__ == "__main__":
  main()
