"""
matrixbot.py — Python client library for the Matrix messenger Bot API.

Matrix is a Telegram-like Iranian messenger whose Bot API mirrors the
Telegram Bot API. The default endpoint is the abarsayeh.ir mirror::

    https://abarsayeh.ir/bot<TOKEN>/<method>

Quick start::

    from matrixbot import MatrixBot, webapp_button, url_button, inline_keyboard

    bot = MatrixBot("123456:ABCDEF...")

    def main_menu():
        return inline_keyboard([
            [webapp_button("🌐  ورود به سایت  ", "https://hastsipnl.isfpardaz.ir/mahan")],
            [url_button("📢  ورود به کانال  ", "https://abarsayeh.ir/Hamster", style="primary")],
            [url_button("💬  پشتیبانی  ", "https://t.me/Mahan1", style="success")],
        ])

    bot.call("sendMessage", chat_id=123456,
             text="به بات خوش آمدید ♥️", reply_markup=main_menu())

    # forced join check
    if bot.is_user_member("@Hamster", user_id):
        ...

Requires: requests  (pip install requests)
"""

import json
import time

import requests

__version__ = "1.0.0"
__all__ = [
    "MatrixBot",
    "MatrixAPIError",
    "MatrixNetworkError",
    "webapp_button",
    "url_button",
    "callback_button",
    "inline_keyboard",
    "reply_keyboard",
    "remove_keyboard",
    "force_reply",
    "DEFAULT_BASE_URL",
]

DEFAULT_BASE_URL = "https://abarsayeh.ir/bot"

# Params that must be JSON-encoded when sent as form fields.
_JSON_FIELDS = {
    "reply_markup",
    "commands",
    "scope",
    "menu_button",
    "allowed_updates",
    "results",      # answerWebAppQuery
    "result",       # answerWebAppQuery (singular form, just in case)
}

# Params that may be an uploaded file (local path -> multipart).
_FILE_FIELDS = {
    "photo",
    "audio",
    "document",
    "video",
    "animation",
    "voice",
    "video_note",
    "sticker",
    "thumb",
    "thumbnail",
}

# getChatMember statuses that count as "in the channel/group".
MEMBER_STATUSES = {"creator", "administrator", "member"}


class MatrixAPIError(Exception):
    """The API answered with ok=false (or an unexpected HTTP status)."""

    def __init__(self, error_code=None, description=None, method=None):
        self.error_code = error_code
        self.description = description
        self.method = method
        super().__init__(
            "Matrix API error%s%s" % (
                " [%s]" % method if method else "",
                ": %s (%s)" % (description, error_code)
                if description else "",
            )
        )


class MatrixNetworkError(MatrixAPIError):
    """Could not reach the API at all (connection error / timeout)."""


class MatrixBot:
    """Thin, friendly wrapper around the Matrix Bot API."""

    def __init__(self, token, base_url=DEFAULT_BASE_URL, file_base_url=None,
                 timeout=30, max_retries=3, backoff=1.0):
        """
        token:        bot token from @BotFather (or the Matrix equivalent).
        base_url:     API endpoint root, token and method are appended:
                      {base_url}/{token}/{method}.  Default: https://abarsayeh.ir/bot
                      Pass "http://abarsayeh.ir/bot" if the mirror needs plain HTTP.
        file_base_url: root for get_file_url(); defaults to {base_url}/file.
        timeout:      seconds for a single HTTP request.
        max_retries:  how many times to retry on network errors / HTTP 429.
        backoff:      base seconds between retries (exponential).
        """
        if not token or not str(token).strip():
            raise ValueError("token is required")
        self.token = str(token).strip()
        self.base_url = base_url.rstrip("/")
        self.file_base_url = (file_base_url or (self.base_url + "/file")).rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff = backoff
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "matrixbot.py/%s" % __version__})

    def __repr__(self):
        return "<MatrixBot base_url=%r>" % self.base_url

    # ------------------------------------------------------------------ core

    def _method_url(self, method):
        return "%s/%s/%s" % (self.base_url, self.token, method)

    def call(self, method, files=None, _params=None, **params):
        """
        Call any API method by name, e.g. bot.call("sendMessage", chat_id=..,
        text=.., reply_markup=..).  `reply_markup` / `commands` style dicts
        and lists are JSON-encoded automatically.  Local file paths passed to
        photo/audio/document/video/... are uploaded as multipart.

        Returns the `result` field.  Raises MatrixAPIError on ok=false,
        MatrixNetworkError when the server is unreachable.
        """
        if _params:
            params = dict(_params, **params)
        data, upload_files = self._prepare(params, files)
        url = self._method_url(method)

        last_exc = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = self._post_and_close(url, data=data,
                                            files=upload_files or None,
                                            timeout=self.timeout)
            except requests.RequestException as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    time.sleep(self.backoff * (2 ** attempt))
                    continue
                raise MatrixNetworkError(
                    description="unreachable: %s" % exc, method=method) from exc

            if resp.status_code == 429:
                retry_after = 1
                try:
                    retry_after = int(resp.json().get("parameters", {})
                                      .get("retry_after", 1))
                except Exception:
                    pass
                if attempt < self.max_retries:
                    time.sleep(min(retry_after, 60))
                    continue

            try:
                payload = resp.json()
            except ValueError as exc:
                raise MatrixAPIError(
                    error_code=resp.status_code,
                    description="non-JSON response: %s" % resp.text[:200],
                    method=method) from exc

            if not payload.get("ok"):
                raise MatrixAPIError(
                    error_code=payload.get("error_code", resp.status_code),
                    description=payload.get("description", "unknown error"),
                    method=method)
            return payload.get("result")

        # Unreachable (mypy/linters); network failures raise above.
        raise MatrixNetworkError(description=str(last_exc), method=method)

    # make bot("sendMessage", ...) work as a shortcut for bot.call(...)
    __call__ = call

    def _prepare(self, params, files):
        """Split params into form fields + multipart files; JSON-encode dicts."""
        data = {}
        upload_files = dict(files or {})
        opened = []
        try:
            for key, value in params.items():
                if value is None:
                    continue
                if key in _JSON_FIELDS and isinstance(value, (dict, list)):
                    data[key] = json.dumps(value, ensure_ascii=False)
                elif (key in _FILE_FIELDS and isinstance(value, str)
                        and self._looks_like_path(value)):
                    fh = open(value, "rb")
                    opened.append(fh)
                    upload_files[key] = fh
                elif hasattr(value, "read"):
                    upload_files[key] = value
                elif isinstance(value, bool):
                    data[key] = "true" if value else "false"
                else:
                    data[key] = value
        except Exception:
            for fh in opened:
                try:
                    fh.close()
                except Exception:
                    pass
            raise
        # NOTE: opened file handles stay open until the request finishes;
        # requests closes them? No — it does not. We close them after post.
        # To keep this simple and safe, callers using paths get files closed
        # in `call` via try/finally below. (See _close_after.)
        self._pending_close = opened
        return data, upload_files

    @staticmethod
    def _looks_like_path(value):
        import os
        return ("/" in value or "\\" in value or value.startswith(".")
                or os.path.exists(value)) and not value.startswith(("http://", "https://"))

    # -- the try/finally closing needs a small wrapper; do it here ----------
    def _post_and_close(self, *args, **kwargs):
        try:
            return self._session.post(*args, **kwargs)
        finally:
            for fh in getattr(self, "_pending_close", []):
                try:
                    fh.close()
                except Exception:
                    pass
            self._pending_close = []

    # ------------------------------------------------------------------ info

    def get_me(self):
        """Basic info about the bot.  -> User"""
        return self.call("getMe")

    def get_updates(self, offset=None, limit=100, timeout=None, allowed_updates=None):
        """Long-poll for updates. Returns a list of Update dicts."""
        return self.call("getUpdates", offset=offset, limit=limit,
                         timeout=timeout if timeout is not None else self.timeout,
                         allowed_updates=allowed_updates)

    def iter_updates(self, timeout=30, limit=100, allowed_updates=None):
        """Yield updates forever, tracking the offset automatically."""
        offset = None
        while True:
            try:
                updates = self.get_updates(offset=offset, limit=limit,
                                           timeout=timeout,
                                           allowed_updates=allowed_updates)
            except MatrixAPIError:
                time.sleep(2)
                continue
            for update in updates or []:
                offset = update["update_id"] + 1
                yield update

    def run(self, handler, **kwargs):
        """Run handler(bot, update) for every incoming update, forever."""
        for update in self.iter_updates(**kwargs):
            try:
                handler(self, update)
            except Exception:
                # Never let one bad update kill the polling loop.
                continue

    # ---------------------------------------------------------------- webhook

    def set_webhook(self, url, **kwargs):
        return self.call("setWebhook", url=url, **kwargs)

    def delete_webhook(self, drop_pending_updates=False):
        return self.call("deleteWebhook",
                         drop_pending_updates=drop_pending_updates or None)

    def get_webhook_info(self):
        return self.call("getWebhookInfo")

    # ---------------------------------------------------------------- members

    def get_chat_member(self, chat_id, user_id):
        """
        -> {"status": "member"|"left"|..., "user": {...}}.
        Canonical name is getChatMember; if your mirror only answers the
        lowercase spelling, use bot.call("getchatmember", chat_id=..,
        user_id=..) instead.
        """
        return self.call("getChatMember", chat_id=chat_id, user_id=user_id)

    def is_user_member(self, chat_id, user_id, fail_open=False):
        """
        Forced-join helper: True when the user is creator/administrator/member
        of the chat/channel.  Any API error -> `fail_open` (default False,
        i.e. fail closed = treat as not a member).
        """
        try:
            member = self.get_chat_member(chat_id, user_id)
        except MatrixAPIError:
            return bool(fail_open)
        return (member or {}).get("status") in MEMBER_STATUSES

    # ---------------------------------------------------------------- messages

    def send_message(self, chat_id, text, parse_mode=None, reply_markup=None,
                     disable_notification=None, reply_to_message_id=None, **kwargs):
        return self.call("sendMessage", chat_id=chat_id, text=text,
                         parse_mode=parse_mode, reply_markup=reply_markup,
                         disable_notification=disable_notification,
                         reply_to_message_id=reply_to_message_id, **kwargs)

    def edit_message_text(self, chat_id, message_id, text, parse_mode=None,
                          reply_markup=None, **kwargs):
        return self.call("editMessageText", chat_id=chat_id,
                         message_id=message_id, text=text,
                         parse_mode=parse_mode, reply_markup=reply_markup,
                         **kwargs)

    def delete_message(self, chat_id, message_id):
        return self.call("deleteMessage", chat_id=chat_id,
                         message_id=message_id)

    def answer_callback_query(self, callback_query_id, text=None,
                              show_alert=False, **kwargs):
        return self.call("answerCallbackQuery",
                         callback_query_id=callback_query_id, text=text,
                         show_alert=show_alert or None, **kwargs)

    def answer_web_app_query(self, web_app_query_id, result):
        """`result` is the InlineQueryResult dict to send."""
        return self.call("answerWebAppQuery",
                         web_app_query_id=web_app_query_id, result=result)

    # ------------------------------------------------------------------ media

    def send_photo(self, chat_id, photo, caption=None, parse_mode=None,
                   reply_markup=None, **kwargs):
        """`photo`: file_id, http(s) URL, or local path (uploaded)."""
        return self.call("sendPhoto", chat_id=chat_id, photo=photo,
                         caption=caption, parse_mode=parse_mode,
                         reply_markup=reply_markup, **kwargs)

    def send_audio(self, chat_id, audio, caption=None, reply_markup=None,
                   **kwargs):
        return self.call("sendAudio", chat_id=chat_id, audio=audio,
                         caption=caption, reply_markup=reply_markup, **kwargs)

    def send_document(self, chat_id, document, caption=None, reply_markup=None,
                      **kwargs):
        return self.call("sendDocument", chat_id=chat_id, document=document,
                         caption=caption, reply_markup=reply_markup, **kwargs)

    def send_video(self, chat_id, video, caption=None, reply_markup=None,
                   **kwargs):
        return self.call("sendVideo", chat_id=chat_id, video=video,
                         caption=caption, reply_markup=reply_markup, **kwargs)

    def send_animation(self, chat_id, animation, caption=None,
                       reply_markup=None, **kwargs):
        return self.call("sendAnimation", chat_id=chat_id, animation=animation,
                         caption=caption, reply_markup=reply_markup, **kwargs)

    def send_voice(self, chat_id, voice, caption=None, reply_markup=None,
                   **kwargs):
        return self.call("sendVoice", chat_id=chat_id, voice=voice,
                         caption=caption, reply_markup=reply_markup, **kwargs)

    def send_video_note(self, chat_id, video_note, reply_markup=None, **kwargs):
        return self.call("sendVideoNote", chat_id=chat_id,
                         video_note=video_note, reply_markup=reply_markup,
                         **kwargs)

    def send_sticker(self, chat_id, sticker, reply_markup=None, **kwargs):
        return self.call("sendSticker", chat_id=chat_id, sticker=sticker,
                         reply_markup=reply_markup, **kwargs)

    def send_location(self, chat_id, latitude, longitude, reply_markup=None,
                      **kwargs):
        return self.call("sendLocation", chat_id=chat_id, latitude=latitude,
                         longitude=longitude, reply_markup=reply_markup,
                         **kwargs)

    def send_venue(self, chat_id, latitude, longitude, title, address,
                   reply_markup=None, **kwargs):
        return self.call("sendVenue", chat_id=chat_id, latitude=latitude,
                         longitude=longitude, title=title, address=address,
                         reply_markup=reply_markup, **kwargs)

    def send_contact(self, chat_id, phone_number, first_name, last_name=None,
                     reply_markup=None, **kwargs):
        return self.call("sendContact", chat_id=chat_id,
                         phone_number=phone_number, first_name=first_name,
                         last_name=last_name, reply_markup=reply_markup,
                         **kwargs)

    def get_file(self, file_id):
        """-> {"file_id":..., "file_path":...}; use get_file_url() for a link."""
        return self.call("getFile", file_id=file_id)

    def get_file_url(self, file_path):
        """Direct download URL for a file_path from get_file()."""
        return "%s/bot%s/%s" % (self.file_base_url, self.token,
                                file_path.lstrip("/"))

    # ---------------------------------------------------------------- commands

    def set_my_commands(self, commands, scope=None, language_code=None):
        """`commands`: [{"command": "start", "description": "..."}, ...]"""
        return self.call("setMyCommands", commands=commands, scope=scope,
                         language_code=language_code)

    def delete_my_commands(self, scope=None, language_code=None):
        return self.call("deleteMyCommands", scope=scope,
                         language_code=language_code)

    def get_my_commands(self, scope=None, language_code=None):
        return self.call("getMyCommands", scope=scope,
                         language_code=language_code)

    def set_chat_menu_button(self, chat_id=None, menu_button=None):
        return self.call("setChatMenuButton", chat_id=chat_id,
                         menu_button=menu_button)

    def get_chat_menu_button(self, chat_id=None):
        return self.call("getChatMenuButton", chat_id=chat_id)


# ---------------------------------------------------------------------------
# Keyboard builders
# ---------------------------------------------------------------------------

def webapp_button(text, url, style="primary"):
    """
    Glassy button that opens a Mini App (Web App).
    ONLY works inside inline keyboards — never in reply keyboards.
    `url` MUST be https:// — plain http is rejected.
    """
    return {"text": text, "web_app": {"url": url}, "style": style}


def url_button(text, url, style="primary"):
    """Plain URL button for inline keyboards."""
    return {"text": text, "url": url, "style": style}


def callback_button(text, callback_data, style="primary"):
    """Button that sends a callback_query to the bot."""
    return {"text": text, "callback_data": callback_data, "style": style}


def inline_keyboard(rows):
    """
    rows: list of rows, each row a list of button dicts, e.g.
        inline_keyboard([
            [webapp_button("🌐  ورود به سایت  ", "https://example.com")],
            [url_button("📢  کانال  ", "https://abarsayeh.ir/Hamster")],
        ])
    """
    return {"inline_keyboard": [list(r) for r in rows]}


def reply_keyboard(rows, resize_keyboard=True, one_time_keyboard=False,
                   input_field_placeholder=None):
    """Bottom-of-chat keyboard. NOTE: web_app buttons do NOT work here."""
    kb = {"keyboard": [list(r) for r in rows],
          "resize_keyboard": resize_keyboard,
          "one_time_keyboard": one_time_keyboard}
    if input_field_placeholder:
        kb["input_field_placeholder"] = input_field_placeholder
    return kb


def remove_keyboard(selective=False):
    return {"remove_keyboard": True, "selective": selective}


def force_reply(selective=False, input_field_placeholder=None):
    fr = {"force_reply": True, "selective": selective}
    if input_field_placeholder:
        fr["input_field_placeholder"] = input_field_placeholder
    return fr
