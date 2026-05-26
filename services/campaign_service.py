"""
BulkWave Pro - Campaign Orchestration Service
Runs the bulk-sending loop in a background thread.
"""

import threading
import queue
import time
import random
from datetime import datetime

from utils.helpers import apply_placeholders, now_str, estimate_completion
from utils.database import Database
from services.whatsapp_service import WhatsAppService


class CampaignService:
    """
    Manages a single bulk-sending campaign.

    The UI layer interacts with this service via:
      - start()  / pause()  / resume()  / stop()
      - log_queue   : queue.Queue of log dict items
      - progress_queue : queue.Queue of progress dict items
    """

    def __init__(self, whatsapp_service: WhatsAppService, db: Database):
        self.wa = whatsapp_service
        self.db = db

        # Threading primitives
        self._thread: threading.Thread | None = None
        self._pause_event = threading.Event()
        self._pause_event.set()          # not paused by default
        self._stop_event = threading.Event()

        # Communication queues (UI polls these)
        self.log_queue: queue.Queue = queue.Queue()
        self.progress_queue: queue.Queue = queue.Queue()

        # State
        self.campaign_id: int | None = None
        self.is_running: bool = False
        self.is_paused: bool = False

    # ─── Control API ──────────────────────────────────────────────────────────

    def start(
        self,
        contacts: list[dict],
        message: str,
        image_path: str | None,
        min_delay: float,
        max_delay: float,
        campaign_name: str = "",
        auto_retry: bool = True,
        max_retries: int = 2,
        turbo_mode: bool = False,
    ):
        """Begin sending. contacts = list of {'phone', 'name'} dicts."""
        if self.is_running:
            return

        self.wa.set_fast_mode(turbo_mode)

        self._stop_event.clear()
        self._pause_event.set()
        self.is_running = True
        self.is_paused = False

        # Create DB record
        if not campaign_name:
            campaign_name = f"Campaign {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        self.campaign_id = self.db.create_campaign(
            name=campaign_name,
            message=message,
            total_contacts=len(contacts),
            has_image=bool(image_path),
        )

        self._thread = threading.Thread(
            target=self._send_loop,
            args=(
                contacts,
                message,
                image_path,
                min_delay,
                max_delay,
                auto_retry,
                max_retries,
                turbo_mode,
            ),
            daemon=True,
        )
        self._thread.start()

    def pause(self):
        self._pause_event.clear()
        self.is_paused = True
        self._log("INFO", "⏸  Campaign paused")

    def resume(self):
        self._pause_event.set()
        self.is_paused = False
        self._log("INFO", "▶  Campaign resumed")

    def stop(self):
        self._stop_event.set()
        self._pause_event.set()   # unblock if currently paused
        self.is_running = False
        self.is_paused = False
        self._log("WARNING", "⏹  Campaign stopped by user")
        if self.campaign_id:
            self.db.complete_campaign(self.campaign_id, status="stopped")

    # ─── Send Loop ────────────────────────────────────────────────────────────

    def _send_loop(
        self,
        contacts: list[dict],
        message: str,
        image_path: str | None,
        min_delay: float,
        max_delay: float,
        auto_retry: bool,
        max_retries: int,
    ):
        total = len(contacts)
        sent = 0
        failed = 0
        final_status = "completed"

        self._log(
            "INFO",
            f"Starting campaign — {total} contacts"
            + (" (⚡ turbo mode)" if turbo_mode else ""),
        )

        try:
            for i, contact in enumerate(contacts):
                # Check stop before each contact
                if self._stop_event.is_set():
                    final_status = "stopped"
                    break

                # Block while paused (unblocked by resume() or stop())
                self._pause_event.wait()

                if self._stop_event.is_set():
                    final_status = "stopped"
                    break

                phone = contact.get("phone", "")
                name = contact.get("name", "")
                personalized = apply_placeholders(message, name=name, number=phone)
                remaining = total - i - 1
                eta = estimate_completion(remaining, min_delay, max_delay)

                self._log(
                    "INFO",
                    f"[{i+1}/{total}] Sending to +{phone} ({name or 'no name'})...",
                )

                success, err = self._send_with_retry(
                    phone,
                    personalized,
                    image_path,
                    max_retries if auto_retry else 1,
                )

                if success:
                    sent += 1
                    self._log("SUCCESS", f"Sent to +{phone} ({name})")
                    self.db.save_contact_result(self.campaign_id, phone, name, "sent")
                    self.db.update_campaign(self.campaign_id, sent_count=sent)
                else:
                    failed += 1
                    self._log("ERROR", f"Failed +{phone}: {err}")
                    self.db.save_contact_result(
                        self.campaign_id, phone, name, "failed", error_message=err
                    )
                    self.db.update_campaign(self.campaign_id, failed_count=failed)

                # Update progress bar after every contact
                self._push_progress(i + 1, total, sent, failed, eta)

                # Inter-message delay — checks stop event every 0.5 s so Stop
                # responds immediately instead of being blocked by a long sleep.
                if i < total - 1 and not self._stop_event.is_set():
                    delay = random.uniform(min_delay, max_delay)
                    self._log("INFO", f"Waiting {delay:.1f}s before next message...")
                    end_time = time.time() + delay
                    while time.time() < end_time and not self._stop_event.is_set():
                        time.sleep(min(0.5, end_time - time.time()))

        except Exception as exc:
            # Catch unexpected errors so the finally block always runs
            final_status = "failed"
            self._log("ERROR", f"Campaign crashed: {exc}")

        finally:
            # This block ALWAYS executes — even on crash or keyboard interrupt.
            # Without it the UI would poll the progress queue forever.
            self.is_running = False
            self.is_paused = False
            self.db.complete_campaign(self.campaign_id, status=final_status)
            self._log(
                "SUCCESS" if final_status == "completed" else "WARNING",
                f"Campaign {final_status} — Sent: {sent}  Failed: {failed}",
            )
            # done=True tells the UI to stop polling and mark the send as complete
            self._push_progress(total, total, sent, failed, "Done", done=True)

    def _send_with_retry(
        self,
        phone: str,
        message: str,
        image_path: str | None,
        max_attempts: int,
    ) -> tuple[bool, str]:
        """Attempt sending up to max_attempts times, with back-off between retries."""
        retry_pause = 2 if self.wa.fast_mode else 5
        for attempt in range(1, max_attempts + 1):
            if self._stop_event.is_set():
                return False, "Stopped"
            try:
                if image_path:
                    ok, err = self.wa.send_image_message(phone, message, image_path)
                else:
                    ok, err = self.wa.send_text_message(phone, message)

                if ok:
                    return True, ""
                if attempt < max_attempts:
                    self._log("WARNING", f"↻  Retry {attempt}/{max_attempts-1} for +{phone}")
                    time.sleep(retry_pause)
            except Exception as e:
                err = str(e)
                if attempt < max_attempts:
                    time.sleep(retry_pause)
        return False, err  # type: ignore[return-value]

    # ─── Queue helpers ────────────────────────────────────────────────────────

    def _log(self, level: str, message: str):
        self.log_queue.put(
            {"level": level, "message": message, "time": now_str()}
        )
        # Also persist to DB
        if self.campaign_id:
            try:
                self.db.add_log(level, message, self.campaign_id)
            except Exception:
                pass

    def _push_progress(
        self,
        current: int,
        total: int,
        sent: int,
        failed: int,
        eta: str,
        done: bool = False,
    ):
        self.progress_queue.put(
            {
                "current": current,
                "total": total,
                "sent": sent,
                "failed": failed,
                "remaining": total - current,
                "eta": eta,
                "done": done,
            }
        )

    # ─── Export helpers ───────────────────────────────────────────────────────

    def export_failed(self, output_path: str) -> tuple[bool, str]:
        """Export failed contacts for the last campaign to an Excel file."""
        if not self.campaign_id:
            return False, "No active campaign"
        try:
            import pandas as pd
            failed = self.db.get_failed_contacts(self.campaign_id)
            if not failed:
                return False, "No failed contacts to export"
            df = pd.DataFrame(failed)
            df.to_excel(output_path, index=False)
            return True, output_path
        except Exception as e:
            return False, str(e)
