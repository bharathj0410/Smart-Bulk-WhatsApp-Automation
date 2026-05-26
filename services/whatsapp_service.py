"""
BulkWave Pro - WhatsApp Web Automation Service

Send strategy:
  TEXT  : URL pre-fills text → focus input → Enter key  (no send-button hunting)
  IMAGE : copy image to Windows clipboard via PowerShell → Ctrl+V into chat
          → caption box → Enter.  WhatsApp Web always treats a clipboard-pasted
          image as a PHOTO (never a sticker), which is why this is the primary
          approach.  File-input injection via the attach menu is kept as fallback.
"""

import os
import time
import subprocess
import urllib.parse
import threading
from pathlib import Path

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.common.exceptions import (
        TimeoutException,
        NoSuchElementException,
        WebDriverException,
    )
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False


# ─── Selector banks ───────────────────────────────────────────────────────────

SELECTORS = {
    # Sidebar chat list → confirms user is logged in
    "chat_list": [
        '//div[@aria-label="Chat list"]',
        '//div[@aria-label="Chats"]',
        '//div[@id="pane-side"]',
        '//div[@data-testid="chat-list"]',
    ],

    # Main compose message input
    "message_input": [
        '//div[@contenteditable="true"][@data-tab="10"]',
        '//div[@contenteditable="true"][@title="Type a message"]',
        '//div[@aria-label="Type a message"][@contenteditable="true"]',
        '//div[@aria-placeholder="Type a message"][@contenteditable="true"]',
        '//div[@role="textbox"][@contenteditable="true"]',
        '//div[contains(@class,"copyable-text")][@contenteditable="true"]',
    ],

    # Caption box that appears inside the image/video preview modal
    "caption_input": [
        # Exact aria-label (WhatsApp uses the Unicode ellipsis character …)
        '//div[@aria-label="Add a caption\u2026"][@contenteditable="true"]',
        '//div[@aria-placeholder="Add a caption\u2026"][@contenteditable="true"]',
        # ASCII ellipsis fallback
        '//div[@aria-label="Add a caption..."][@contenteditable="true"]',
        '//div[@aria-placeholder="Add a caption..."][@contenteditable="true"]',
        # Partial match — covers locale variations
        '//div[contains(@aria-label,"caption")][@contenteditable="true"]',
        '//div[contains(@aria-placeholder,"caption")][@contenteditable="true"]',
        # data-tab based (varies by WhatsApp Web version)
        '//div[@contenteditable="true"][@data-tab="7"]',
        '//div[@contenteditable="true"][@data-tab="6"]',
        '//div[@contenteditable="true"][@data-tab="5"]',
        # Inside the media-preview footer/panel (structural selector)
        '//footer//div[@contenteditable="true"]',
        '//*[contains(@class,"media-caption")]//div[@contenteditable="true"]',
        '//*[contains(@class,"caption")]//div[@contenteditable="true"]',
    ],

    # Paperclip / attachment button
    "attach_button": [
        '//div[@title="Attach"]',
        '//button[@aria-label="Attach"]',
        '//span[@data-icon="attach-menu-plus"]',
        '//span[@data-icon="plus"]',
        '//span[@data-icon="clip"]',
    ],

    # "Photos & Videos" option that appears after clicking the attach button
    "photos_option": [
        '//span[contains(text(),"Photos & Videos")]',
        '//span[contains(text(),"Photos")]',
        '//*[@aria-label="Photos & Videos"]',
        '//*[contains(@aria-label,"Photo")]',
        '//input[@accept="image/*,video/mp4,video/3gpp,video/quicktime"]',
    ],

    # Send button (fallback only — Enter key on caption box is primary).
    # Covers both the compose-box send button AND the image-preview send button.
    "send_button": [
        '//button[@aria-label="Send"]',
        '//div[@role="button"][@aria-label="Send"]',
        '//span[@data-icon="send"]/..',       # click the parent button
        '//span[@data-icon="send"]',
        '//button[@data-testid="compose-btn-send"]',
        '//div[@data-testid="send"]',
        # Image/media preview modal send button
        '//div[contains(@class,"media-send")]//button',
        '//*[@data-testid="media-forward-button"]',
        '//*[@data-testid="send-media-btn"]',
    ],

    # Popups WhatsApp shows for new contacts
    "popup_buttons": [
        '//*[contains(text(),"Continue to Chat")]',
        '//*[contains(text(),"Continue")]',
        '//button[contains(text(),"OK")]',
    ],

    # Invalid-number / not-on-WhatsApp indicators.
    # WhatsApp Web shows these when a number is wrong or not registered.
    "invalid_phone": [
        # "Phone number shared via url is invalid"
        '//*[contains(text(),"phone number shared via url is invalid")]',
        '//*[contains(translate(text(),'
        '"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz"),'
        '"phone number shared via url is invalid")]',
        # "This phone number is not registered on WhatsApp"
        '//*[contains(text(),"not registered on WhatsApp")]',
        '//*[contains(translate(text(),'
        '"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz"),'
        '"not registered on whatsapp")]',
        # "X is not on WhatsApp"
        '//*[contains(text(),"is not on WhatsApp")]',
        '//*[contains(translate(text(),'
        '"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz"),'
        '"is not on whatsapp")]',
        # Generic "invalid phone" dialog title
        '//*[contains(translate(text(),'
        '"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz"),'
        '"invalid phone")]',
        # WhatsApp error alert / popup container
        '//*[@data-testid="alert-dialog"]',
        '//*[contains(@class,"alert")]//h1[contains(text(),"Invalid")]',
    ],
}


class WhatsAppService:
    """Controls a Chrome browser session to interact with WhatsApp Web."""

    def __init__(self, session_path: str = "", fast_mode: bool = False):
        if not SELENIUM_AVAILABLE:
            raise RuntimeError(
                "Selenium is not installed. Run:  pip install selenium webdriver-manager"
            )
        self.session_path = session_path or str(
            Path(__file__).parent.parent / "chrome_data"
        )
        self.driver: "webdriver.Chrome | None" = None
        self.is_connected = False
        self.fast_mode = fast_mode
        self._lock = threading.Lock()

    def set_fast_mode(self, enabled: bool) -> None:
        """Enable minimal internal waits for turbo sending."""
        self.fast_mode = enabled

    def _pause(self, normal: float, fast: float | None = None) -> None:
        """Sleep for `normal` seconds, or a shorter `fast` duration in turbo mode."""
        time.sleep(fast if self.fast_mode and fast is not None else normal)

    # ═══════════════════════════════════════════════════════════════════════════
    # Browser lifecycle
    # ═══════════════════════════════════════════════════════════════════════════

    def initialize_browser(self, headless: bool = False) -> tuple[bool, str]:
        """Launch Chrome with a persistent profile pointed at WhatsApp Web."""
        try:
            options = webdriver.ChromeOptions()
            options.add_argument(f"--user-data-dir={os.path.abspath(self.session_path)}")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1280,900")
            options.add_argument("--log-level=3")
            options.add_argument("--disable-notifications")
            options.add_experimental_option("excludeSwitches", ["enable-logging"])
            # Don't wait for every asset — we poll for the compose box instead.
            options.page_load_strategy = "none" if self.fast_mode else "eager"

            if headless:
                options.add_argument("--headless=new")

            service = ChromeService(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            self.driver.set_page_load_timeout(30)
            self.driver.get("https://web.whatsapp.com")
            return True, ""
        except Exception as e:
            return False, str(e)

    def wait_for_login(self, timeout: int = 120, callback=None) -> bool:
        """Block until WhatsApp Web shows the chat list (logged in) or timeout."""
        start = time.time()
        while time.time() - start < timeout:
            if self._any_present(SELECTORS["chat_list"]):
                self.is_connected = True
                return True
            if callback:
                callback(f"Waiting for QR scan… ({int(time.time()-start)}s)")
            time.sleep(3)
        return False

    def is_logged_in(self) -> bool:
        try:
            return self._any_present(SELECTORS["chat_list"])
        except Exception:
            return False

    def close(self):
        try:
            if self.driver:
                self.driver.quit()
        except Exception:
            pass
        finally:
            self.driver = None
            self.is_connected = False

    # ═══════════════════════════════════════════════════════════════════════════
    # Public send API
    # ═══════════════════════════════════════════════════════════════════════════

    def send_text_message(self, phone: str, text: str) -> tuple[bool, str]:
        """
        Send a plain-text WhatsApp message.

        Flow: navigate with text pre-filled in URL → focus input → press Enter.
        No send-button selector needed → immune to WhatsApp DOM changes.
        """
        with self._lock:
            try:
                encoded = urllib.parse.quote(text)
                self.driver.get(
                    f"https://web.whatsapp.com/send?phone={phone}&text={encoded}"
                )

                self._dismiss_popup()

                msg_input = self._find_message_input(timeout=35)
                if msg_input is None:
                    if self._any_present(SELECTORS["invalid_phone"]):
                        return False, "Number not on WhatsApp / invalid"
                    return False, "Chat did not open — message input not found"

                time.sleep(0.6)

                # Move cursor to END of the pre-filled text.
                # A click can land in the middle of the text, causing Enter
                # to insert a newline rather than send the message.
                msg_input.send_keys(Keys.END)
                time.sleep(0.3)
                msg_input.send_keys(Keys.ENTER)
                time.sleep(1.5)
                return True, "Sent"

            except Exception as e:
                return False, str(e)

    def send_image_message(
        self, phone: str, caption: str, image_path: str
    ) -> tuple[bool, str]:
        """
        Send an image as a PHOTO (never a sticker or document).

        Primary flow — clipboard paste:
          1. Copy image to Windows clipboard via PowerShell.
          2. Open the chat, click the compose area, press Ctrl+V.
             WhatsApp Web always treats a clipboard-pasted image as a photo.
          3. Find the caption box, type text, press Enter.

        Fallback flow — file-input injection (if clipboard fails):
          1. Open chat.
          2. Click the paperclip → find the Photos file input → send_keys(path).
          3. Caption box → Enter.
        """
        with self._lock:
            try:
                abs_image = os.path.abspath(image_path)
                if not os.path.isfile(abs_image):
                    return False, f"Image not found: {abs_image}"

                # ── Step 1: open the chat ─────────────────────────────────────
                self.driver.get(f"https://web.whatsapp.com/send?phone={phone}")
                self._dismiss_popup()

                msg_input = self._find_message_input(timeout=35)
                if msg_input is None:
                    if self._any_present(SELECTORS["invalid_phone"]):
                        return False, "Number not on WhatsApp / invalid"
                    return False, "Chat did not open"

                self._pause(0.5, 0.15)

                # Save the compose-box element ID so _find_caption_box can
                # explicitly exclude it in every tier — prevents it from
                # mistaking the compose box for the caption input.
                compose_id = msg_input.id

                # ── Step 2: deliver the image ──────────────────────────────────
                # PRIMARY: clipboard paste — guaranteed to arrive as photo.
                clipboard_ok = self._paste_image_via_clipboard(abs_image, msg_input)

                if not clipboard_ok:
                    # FALLBACK: inject into the Photos file input via attach menu.
                    attach = self._find_clickable(
                        SELECTORS["attach_button"], timeout=10
                    )
                    if attach is None:
                        return False, "Attach button not found"
                    self._safe_click(attach)

                    photos_input = self._get_photos_input()
                    if photos_input is None:
                        return False, "Photos & Videos file input not found in attach menu"

                    self.driver.execute_script(
                        "arguments[0].style.cssText='display:block!important;"
                        "visibility:visible!important;opacity:1!important;';",
                        photos_input,
                    )
                    photos_input.send_keys(abs_image)

                # ── Step 3: wait for the preview modal to fully render ─────────
                # Without this pause _find_caption_box runs before the modal
                # appears and wrongly returns the compose box as the caption box,
                # causing the caption to be sent as a plain text message instead.
                time.sleep(2.5)

                # ── Step 4: find the caption box ──────────────────────────────
                # Pass compose_id so every tier can skip the compose box.
                cap_box = self._find_caption_box(timeout=10, compose_id=compose_id)

                # ── Step 5: type caption ───────────────────────────────────────
                if caption and cap_box:
                    self._safe_click(cap_box)
                    time.sleep(0.4)
                    cap_box.send_keys(caption)
                    time.sleep(0.8)

                # ── Step 6: send ───────────────────────────────────────────────
                # IMPORTANT: never use active_element.send_keys(ENTER) here —
                # if cap_box was None, the active element might be the compose
                # box, and pressing Enter would send an empty/wrong text message.
                sent = False
                if cap_box:
                    try:
                        cap_box.send_keys(Keys.ENTER)
                        sent = True
                    except Exception:
                        pass

                if not sent:
                    # Find the send button specific to the image preview modal
                    send_btn = self._find_clickable(
                        SELECTORS["send_button"], timeout=5
                    )
                    if send_btn:
                        self._safe_click(send_btn)
                        sent = True

                if not sent:
                    return False, "Could not trigger send after image upload"

                time.sleep(2.0)
                return True, "Sent"

            except Exception as e:
                return False, str(e)

    # ═══════════════════════════════════════════════════════════════════════════
    # Private helpers
    # ═══════════════════════════════════════════════════════════════════════════

    def _paste_image_via_clipboard(self, abs_image_path: str, msg_input) -> bool:
        """
        Copy an image file to the Windows clipboard using PowerShell, then
        paste it into the WhatsApp Web compose area with Ctrl+V.

        WhatsApp Web always treats a clipboard-pasted image as a PHOTO — it
        never becomes a sticker or document regardless of which file input was
        previously focused.  This is the most reliable way to send an image.

        Returns True on success, False if PowerShell is unavailable or fails
        (in which case the caller falls back to the file-input approach).
        """
        try:
            # Escape single-quotes for PowerShell string literal
            escaped = abs_image_path.replace("'", "''")
            ps_script = (
                "Add-Type -AssemblyName System.Windows.Forms; "
                "Add-Type -AssemblyName System.Drawing; "
                "[System.Windows.Forms.Clipboard]::SetImage("
                f"[System.Drawing.Image]::FromFile('{escaped}'))"
            )
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    ps_script,
                ],
                capture_output=True,
                timeout=15,
            )
            if result.returncode != 0:
                return False

            # Small pause to ensure clipboard is populated before pasting
            self._pause(0.4, 0.15)

            # Focus the compose area and paste
            self._safe_click(msg_input)
            self._pause(0.2, 0.05)
            msg_input.send_keys(Keys.CONTROL + "v")
            return True

        except Exception:
            return False

    def _get_photos_input(self):
        """
        Return the Photos & Videos <input type="file"> from the attach menu
        WITHOUT clicking the menu label (which opens the OS file-picker dialog).

        Strategy — three tiers, most reliable first:

        Tier 1 — DOM proximity (most reliable)
            Locate the "Photos & Videos" text element, then traverse the DOM
            to the nearest ancestor <label> and find its <input type="file">.
            WhatsApp wraps each attach option inside a <label>, so the file
            input we find this way is guaranteed to be the Photos one.

        Tier 2 — Direct accept-attribute XPath
            Look for a file input whose 'accept' attribute explicitly contains
            a video MIME type (photos/videos inputs are the only ones that do).

        Tier 3 — Scoring fallback
            Inspect every file input on the page and pick the best by score
            (same logic as before, kept as a last resort).
        """
        # Give the attach-menu DOM a moment to render after the paperclip click
        time.sleep(0.7)

        # ── Tier 1: proximity to the "Photos & Videos" menu text ─────────────
        proximity_xpaths = [
            # Input inside the same <label> as the Photos & Videos span
            '//span[contains(text(),"Photos & Videos")]'
            '/ancestor::label//input[@type="file"]',
            '//span[contains(text(),"Photos")]'
            '/ancestor::label//input[@type="file"]',
            # Input inside the parent/grandparent div of the span
            '//span[contains(text(),"Photos & Videos")]'
            '/..//input[@type="file"]',
            '//span[contains(text(),"Photos & Videos")]'
            '/../..//input[@type="file"]',
            '//span[contains(text(),"Photos")]'
            '/..//input[@type="file"]',
            # aria-label variants
            '//*[@aria-label="Photos & Videos"]'
            '/ancestor::label//input[@type="file"]',
            '//*[@aria-label="Photos & Videos"]'
            '/..//input[@type="file"]',
            '//*[@title="Photos & Videos"]'
            '/ancestor::label//input[@type="file"]',
        ]
        for xpath in proximity_xpaths:
            try:
                el = self.driver.find_element(By.XPATH, xpath)
                if el is not None:
                    return el
            except (NoSuchElementException, Exception):
                continue

        # ── Tier 2: accept-attribute XPath (Photos inputs always include video)
        accept_xpaths = [
            '//input[@type="file"][contains(@accept,"video/mp4")]',
            '//input[@type="file"][contains(@accept,"video/3gpp")]',
            '//input[@type="file"][contains(@accept,"video/quicktime")]',
            # Broad "video" keyword — avoids sticker (image/webp only) and
            # document (accept="*") inputs
            '//input[@type="file"][contains(@accept,"video")]',
        ]
        for xpath in accept_xpaths:
            try:
                el = self.driver.find_element(By.XPATH, xpath)
                if el is not None:
                    # Extra safety: reject if it looks like a sticker input
                    accept = (el.get_attribute("accept") or "").lower()
                    if "image/webp" in accept and "video" not in accept:
                        continue
                    return el
            except (NoSuchElementException, Exception):
                continue

        # ── Tier 3: scoring fallback ──────────────────────────────────────────
        return self._find_photos_file_input()

    def _find_photos_file_input(self):
        """
        Scoring-based fallback: inspect every <input type="file"> and pick the
        one whose 'accept' attribute best matches the Photos & Videos input.
        Penalises sticker (image/webp-only) and document (accept=*) inputs.
        """
        try:
            inputs = self.driver.find_elements(By.XPATH, '//input[@type="file"]')
            best, best_score = None, -999

            for inp in inputs:
                accept = (inp.get_attribute("accept") or "").lower()
                score = 0
                if "image/*" in accept:
                    score += 5
                if "video/mp4" in accept:
                    score += 6          # strongest signal of Photos & Videos input
                if "video/3gpp" in accept:
                    score += 3
                if "video/quicktime" in accept:
                    score += 2
                if "video" in accept and "mp4" not in accept and "3gpp" not in accept:
                    score += 1          # some other video format — still likely photos
                if "image/webp" in accept and "video" not in accept:
                    score -= 20         # sticker input — heavily penalise
                if accept in ("*", ""):
                    score -= 10         # document input
                if "application" in accept:
                    score -= 10

                if score > best_score:
                    best_score = score
                    best = inp

            return best if best_score > 0 else None
        except Exception:
            return None

    def _find_message_input(self, timeout: int = 30):
        """
        Return the visible compose message input, or None after timeout.

        Also performs a periodic early-exit check for WhatsApp's
        "invalid / not on WhatsApp" error messages so we don't burn the full
        timeout (up to 35 s) on a number that will never open a chat.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            # Early exit: number is invalid or not registered on WhatsApp
            if self._any_present(SELECTORS["invalid_phone"]):
                return None

            for sel in SELECTORS["message_input"]:
                try:
                    el = self.driver.find_element(By.XPATH, sel)
                    if el.is_displayed():
                        return el
                except NoSuchElementException:
                    continue
            self._pause(0.5, 0.12)
        return None

    def _find_caption_box(self, timeout: int = 6, compose_id: str | None = None):
        """
        Return the caption input inside WhatsApp Web's image preview modal.

        compose_id — Selenium internal ID of the compose box.  Every tier
        explicitly skips this element so we never mistake the chat compose
        box for the caption box (which would cause text to be sent as a
        separate message instead of as the image caption).

        Three-tier search (most → least reliable):

        Tier 1 — Active element
            The preview modal auto-focuses the caption input; Ctrl+V also
            moves focus there.  We check the currently focused element and
            return it if it is a contenteditable div that is not the compose
            box (matched by data-tab AND by Selenium element ID).

        Tier 2 — Specific aria-label / placeholder selectors
            Multiple XPath selectors covering different WhatsApp Web versions.

        Tier 3 — Positive-signal fallback
            Only returns a contenteditable element that has a POSITIVE caption
            signal ("caption" in its aria-label / aria-placeholder) OR that
            sits inside a media-preview modal container (detected via JS).
            The broad "anything that is not the compose box" heuristic has
            been removed — it caused false matches on search boxes and other
            UI elements when the preview modal had not yet appeared.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:

            # ── Tier 1: active element ────────────────────────────────────────
            try:
                active = self.driver.switch_to.active_element
                if (
                    active.tag_name.lower() == "div"
                    and active.get_attribute("contenteditable") == "true"
                    and active.is_displayed()
                    # Skip by data-tab (compose box is tab 10 in most versions)
                    and (active.get_attribute("data-tab") or "") != "10"
                    # Skip by element ID — works even when data-tab differs
                    and (compose_id is None or active.id != compose_id)
                ):
                    return active
            except Exception:
                pass

            # ── Tier 2: explicit selectors ────────────────────────────────────
            for sel in SELECTORS["caption_input"]:
                try:
                    el = self.driver.find_element(By.XPATH, sel)
                    if el.is_displayed() and (
                        compose_id is None or el.id != compose_id
                    ):
                        return el
                except NoSuchElementException:
                    continue

            # ── Tier 3: positive-signal-only fallback ─────────────────────────
            try:
                all_ce = self.driver.find_elements(
                    By.XPATH, '//div[@contenteditable="true"]'
                )
                for el in all_ce:
                    try:
                        if not el.is_displayed():
                            continue
                        # Exclude the compose box by ID and by data-tab
                        if compose_id and el.id == compose_id:
                            continue
                        if (el.get_attribute("data-tab") or "") == "10":
                            continue

                        aria = (el.get_attribute("aria-label") or "").lower()
                        ph = (el.get_attribute("aria-placeholder") or "").lower()

                        # Positive signal 1: aria/placeholder says "caption"
                        if "caption" in aria or "caption" in ph:
                            return el

                        # Positive signal 2: element lives inside a preview modal
                        in_modal = self.driver.execute_script(
                            "const e=arguments[0];"
                            "return !!(e.closest('[data-testid*=\"preview\"]')"
                            "|| e.closest('[data-testid*=\"media\"]')"
                            "|| e.closest('[class*=\"preview\"]')"
                            "|| e.closest('[class*=\"media-upload\"]'));",
                            el,
                        )
                        if in_modal:
                            return el

                    except Exception:
                        continue
            except Exception:
                pass

            time.sleep(0.4)

        return None

    def _find_clickable(self, selectors: list[str], timeout: int = 10):
        """Return the first clickable element matching any selector, or None."""
        per = max(timeout // max(len(selectors), 1), 2)
        for sel in selectors:
            try:
                return WebDriverWait(self.driver, per).until(
                    EC.element_to_be_clickable((By.XPATH, sel))
                )
            except TimeoutException:
                continue
        return None

    def _dismiss_popup(self):
        """
        Dismiss the 'Continue to Chat' popup WhatsApp shows for new contacts.
        Uses short per-selector timeout so it doesn't add noticeable lag when
        no popup is present.
        """
        for sel in SELECTORS["popup_buttons"]:
            try:
                btn = WebDriverWait(self.driver, 2).until(
                    EC.element_to_be_clickable((By.XPATH, sel))
                )
                btn.click()
                self._pause(0.8, 0.2)
                return
            except (TimeoutException, Exception):
                continue

    def _safe_click(self, element):
        """Selenium click with JS fallback."""
        try:
            element.click()
        except Exception:
            try:
                self.driver.execute_script("arguments[0].click();", element)
            except Exception:
                pass

    def _any_present(self, selectors: list[str]) -> bool:
        """Return True if any selector finds an element currently in the DOM."""
        for sel in selectors:
            try:
                self.driver.find_element(By.XPATH, sel)
                return True
            except (NoSuchElementException, WebDriverException):
                continue
        return False
