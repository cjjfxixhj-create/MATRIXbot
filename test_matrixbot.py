"""Unit tests for matrixbot.py — no network, no real token."""
import io
import json
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

import requests

import matrixbot
from matrixbot import (
    MatrixBot, MatrixAPIError, MatrixNetworkError,
    webapp_button, url_button, callback_button, inline_keyboard,
    reply_keyboard,
)


def ok_response(result):
    resp = Mock()
    resp.status_code = 200
    resp.json.return_value = {"ok": True, "result": result}
    return resp


def err_response(code=400, desc="Bad Request"):
    resp = Mock()
    resp.status_code = code
    resp.json.return_value = {"ok": False, "error_code": code,
                             "description": desc}
    return resp


def make_bot(**kw):
    bot = MatrixBot("TESTTOKEN", **kw)
    bot._session = Mock()
    return bot


class TestCore(unittest.TestCase):
    def test_url_construction(self):
        bot = make_bot()
        bot._session.post.return_value = ok_response({"id": 1})
        bot.call("sendMessage", chat_id=5, text="hi")
        url = bot._session.post.call_args[0][0]
        self.assertEqual(url,
                         "https://abarsayeh.ir/bot/TESTTOKEN/sendMessage")

    def test_custom_base_url(self):
        bot = make_bot(base_url="http://abarsayeh.ir/bot")
        bot._session.post.return_value = ok_response(True)
        bot.get_me()
        url = bot._session.post.call_args[0][0]
        self.assertTrue(url.startswith("http://abarsayeh.ir/bot/TESTTOKEN/getMe"))

    def test_reply_markup_json_encoded(self):
        bot = make_bot()
        bot._session.post.return_value = ok_response({"message_id": 7})
        kb = inline_keyboard([[url_button("x", "https://example.com")]])
        bot.send_message(5, "hi", reply_markup=kb)
        data = bot._session.post.call_args[1]["data"]
        self.assertEqual(json.loads(data["reply_markup"]), kb)

    def test_returns_result(self):
        bot = make_bot()
        bot._session.post.return_value = ok_response({"first_name": "Wolfy"})
        self.assertEqual(bot.get_me(), {"first_name": "Wolfy"})

    def test_ok_false_raises(self):
        bot = make_bot()
        bot._session.post.return_value = err_response(400, "Bad Request: chat not found")
        with self.assertRaises(MatrixAPIError) as cm:
            bot.send_message(5, "hi")
        self.assertEqual(cm.exception.error_code, 400)
        self.assertIn("chat not found", cm.exception.description)

    def test_network_error_retries_then_raises(self):
        bot = make_bot(max_retries=2, backoff=0)
        bot._session.post.side_effect = requests.ConnectionError("down")
        with self.assertRaises(MatrixNetworkError):
            bot.get_me()
        self.assertEqual(bot._session.post.call_count, 3)

    def test_retry_then_success(self):
        bot = make_bot(max_retries=2, backoff=0)
        bot._session.post.side_effect = [
            requests.Timeout("slow"),
            ok_response({"ok_id": 1}),
        ]
        self.assertEqual(bot.get_me(), {"ok_id": 1})
        self.assertEqual(bot._session.post.call_count, 2)

    def test_bool_serialized(self):
        bot = make_bot()
        bot._session.post.return_value = ok_response(True)
        bot.answer_callback_query("cq1", show_alert=True)
        data = bot._session.post.call_args[1]["data"]
        self.assertEqual(data["show_alert"], "true")

    def test_none_params_dropped(self):
        bot = make_bot()
        bot._session.post.return_value = ok_response(True)
        bot.send_message(5, "hi", parse_mode=None)
        data = bot._session.post.call_args[1]["data"]
        self.assertNotIn("parse_mode", data)

    def test_empty_token_rejected(self):
        with self.assertRaises(ValueError):
            MatrixBot("  ")


class TestMembers(unittest.TestCase):
    def test_is_member_true(self):
        bot = make_bot()
        bot._session.post.return_value = ok_response(
            {"status": "member",
             "user": {"id": 1780243200, "first_name": "Daniyel",
                      "is_bot": False}})
        self.assertTrue(bot.is_user_member("@Hamster", 1780243200))
        url = bot._session.post.call_args[0][0]
        self.assertTrue(url.endswith("/getChatMember"))

    def test_is_member_false_when_left(self):
        bot = make_bot()
        bot._session.post.return_value = ok_response(
            {"status": "left",
             "user": {"id": 1780243200, "first_name": "Daniyel",
                      "is_bot": False}})
        self.assertFalse(bot.is_user_member("@Hamster", 1780243200))

    def test_is_member_admin_counts(self):
        bot = make_bot()
        bot._session.post.return_value = ok_response({"status": "administrator"})
        self.assertTrue(bot.is_user_member("@Hamster", 1))

    def test_is_member_api_error_fail_closed(self):
        bot = make_bot()
        bot._session.post.return_value = err_response(400, "Bad Request")
        self.assertFalse(bot.is_user_member("@Hamster", 1))

    def test_is_member_api_error_fail_open(self):
        bot = make_bot()
        bot._session.post.return_value = err_response(400, "Bad Request")
        self.assertTrue(bot.is_user_member("@Hamster", 1, fail_open=True))


class TestKeyboards(unittest.TestCase):
    def test_webapp_button(self):
        b = webapp_button("🌐  ورود به سایت  ", "https://hastsipnl.isfpardaz.ir/mahan")
        self.assertEqual(b, {
            "text": "🌐  ورود به سایت  ",
            "web_app": {"url": "https://hastsipnl.isfpardaz.ir/mahan"},
            "style": "primary",
        })

    def test_inline_keyboard(self):
        kb = inline_keyboard([
            [webapp_button("a", "https://example.com")],
            [url_button("b", "https://example.org", style="success")],
        ])
        self.assertEqual(len(kb["inline_keyboard"]), 2)
        self.assertEqual(kb["inline_keyboard"][0][0]["web_app"]["url"],
                         "https://example.com")

    def test_callback_button(self):
        b = callback_button("hit", "hit_cb")
        self.assertEqual(b["callback_data"], "hit_cb")

    def test_reply_keyboard(self):
        kb = reply_keyboard([["a", "b"]])
        self.assertTrue(kb["resize_keyboard"])
        self.assertEqual(kb["keyboard"], [["a", "b"]])


class TestFiles(unittest.TestCase):
    def test_local_path_uploaded(self):
        bot = make_bot()
        bot._session.post.return_value = ok_response({"message_id": 1})
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as fh:
            fh.write(b"fakeimg")
            path = fh.name
        try:
            bot.send_photo(5, path, caption="c")
            kwargs = bot._session.post.call_args[1]
            self.assertIn("photo", kwargs["files"])
            self.assertNotIn(path, str(kwargs["data"].get("photo", "")))
        finally:
            os.unlink(path)

    def test_file_id_not_uploaded(self):
        bot = make_bot()
        bot._session.post.return_value = ok_response({"message_id": 1})
        bot.send_photo(5, "AgACAgQAAxkBAAIB")
        kwargs = bot._session.post.call_args[1]
        self.assertFalse(kwargs["files"])
        self.assertEqual(kwargs["data"]["photo"], "AgACAgQAAxkBAAIB")

    def test_get_file_url(self):
        bot = make_bot()
        url = bot.get_file_url("photos/file_1.jpg")
        self.assertEqual(
            url,
            "https://abarsayeh.ir/bot/file/botTESTTOKEN/photos/file_1.jpg")


class TestPolling(unittest.TestCase):
    def test_iter_updates_tracks_offset(self):
        bot = make_bot()
        bot._session.post.side_effect = [
            ok_response([{"update_id": 10, "message": {"text": "a"}},
                         {"update_id": 11, "message": {"text": "b"}}]),
            ok_response([{"update_id": 12, "message": {"text": "c"}}]),
        ]
        gen = bot.iter_updates()
        try:
            u1 = next(gen)
            u2 = next(gen)
            u3 = next(gen)  # triggers 2nd getUpdates with offset=12
        finally:
            gen.close()
        self.assertEqual((u1["update_id"], u2["update_id"], u3["update_id"]),
                         (10, 11, 12))
        # second getUpdates call must carry offset=12
        second_data = bot._session.post.call_args_list[1][1]["data"]
        self.assertEqual(second_data["offset"], 12)


if __name__ == "__main__":
    unittest.main(verbosity=2)
