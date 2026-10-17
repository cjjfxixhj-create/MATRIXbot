"""
example.py — Matrix bot example: forced join + WebApp glassy menu.

Run:  python3 example.py
(put your real token in MATRIX_TOKEN below or in the MATRIX_BOT_TOKEN env var)
"""
import os

from matrixbot import (
    MatrixBot, MatrixAPIError,
    webapp_button, url_button, inline_keyboard,
)

TOKEN = os.environ.get("MATRIX_BOT_TOKEN", "PUT_YOUR_TOKEN_HERE")
REQUIRED_CHANNEL = "@Hamster"   # کانال جوین اجباری

bot = MatrixBot(TOKEN)  # base_url پیش‌فرض: https://abarsayeh.ir/bot


def main_menu():
    return inline_keyboard([
        [webapp_button("🌐  ورود به سایت  ", "https://hastsipnl.isfpardaz.ir/mahan")],
        [url_button("📢  ورود به کانال  ", "https://abarsayeh.ir/Hamster", style="primary")],
        [url_button("💬  پشتیبانی  ", "https://t.me/Mahan1", style="success")],
    ])


def handle_start(chat_id, user_id):
    # جوین اجباری
    if not bot.is_user_member(REQUIRED_CHANNEL, user_id):
        bot.send_message(
            chat_id,
            "اول عضو کانال شو بعد بیا ♥️",
            reply_markup=inline_keyboard([
                [url_button("📢  ورود به کانال  ", "https://abarsayeh.ir/Hamster",
                            style="primary")],
            ]),
        )
        return
    bot.call("sendMessage", chat_id=chat_id,
             text="به بات خوش آمدید ♥️",
             reply_markup=main_menu())


def main():
    me = bot.get_me()
    print("Bot:", me.get("first_name"), "@%s" % me.get("username"))
    print("Listening... (Ctrl+C to stop)")
    for update in bot.iter_updates():
        msg = update.get("message") or {}
        text = msg.get("text", "")
        if text.startswith("/start"):
            try:
                handle_start(msg["chat"]["id"], msg["from"]["id"])
            except MatrixAPIError as e:
                print("API error:", e)


if __name__ == "__main__":
    main()
