# matrixbot.py — کتابخونه پایتون برای ربات ماتریکس

کلاینت سبک و تمیز برای Bot API ماتریکس (کپی تلگرام). همه متدهایی که خواستی
توش هست + دکمه شیشه‌ای WebApp + جوین اجباری.

## نصب

```bash
pip install git+https://github.com/cjjfxixhj-create/MATRIXbot.git
```

(`requests` خودش با همین دستور نصب میشه.)

## شروع سریع

```python
from matrixbot import MatrixBot, webapp_button, url_button, inline_keyboard

bot = MatrixBot("TOKEN")

def main_menu():
    return inline_keyboard([
        [webapp_button("🌐  ورود به سایت  ", "https://hastsipnl.isfpardaz.ir/mahan")],
        [url_button("📢  ورود به کانال  ", "https://abarsayeh.ir/Hamster", style="primary")],
        [url_button("💬  پشتیبانی  ", "https://t.me/Mahan1", style="success")],
    ])

bot.call("sendMessage", chat_id=123456, text="به بات خوش آمدید ♥️",
         reply_markup=main_menu())

# جوین اجباری
if bot.is_user_member("@Hamster", user_id):
    ...
```

## متدها

همه اینا متد آماده دارن (علاوه بر `call("methodName", ...)` خام):

`getMe` `getUpdates` `setWebhook` `deleteWebhook` `getWebhookInfo`
`deleteMessage` `setMyCommands` `deleteMyCommands` `getMyCommands`
`setChatMenuButton` `getChatMenuButton` `sendMessage` `sendPhoto`
`sendAudio` `sendDocument` `sendVideo` `sendAnimation` `sendVoice`
`sendVideoNote` `sendLocation` `sendVenue` `sendContact` `sendSticker`
`getFile` `answerWebAppQuery` `answerCallbackQuery` `editMessageText`
`getChatMember`

نام پایتونی‌شون snake_caseـه: `bot.send_message(...)`، `bot.get_chat_member(...)`.

## نکات مهم

- **base URL**: پیش‌فرض `https://abarsayeh.ir/bot`ـه. اگه سرورت HTTP می‌خواد:
  `MatrixBot(token, base_url="http://abarsayeh.ir/bot")`
- **getChatMember**: اسم استاندارد `getChatMember`ـه. اگه میرت فقط حروف کوچیک
  (`getchatmember`) رو جواب داد، از `bot.call("getchatmember", chat_id=..., user_id=...)` استفاده کن.
- **دکمه شیشه‌ای (web_app)** فقط توی `inline_keyboard` کار می‌کنه، توی
  `reply_keyboard` نه.
- لینک دکمه web_app باید **HTTPS** باشه؛ HTTP رد میشه.
- فایل لوکال (مسیر فایل) به `send_photo` و بقیه بدی، خودش multipart آپلود می‌کنه؛
  file_id یا URL بدی همون رو می‌فرسته.
- خطای API میشه `MatrixAPIError` (کد و توضیح داره)؛ قطعی شبکه میشه
  `MatrixNetworkError` و خودش چند بار retry می‌کنه.

## فایل‌ها

- `matrixbot.py` — خود کتابخونه (تک‌فایل)
- `example.py` — مثال جوین اجباری + منوی شیشه‌ای
- `test_matrixbot.py` — تست‌ها: `python3 test_matrixbot.py`

⚠️ توکن رو هیچ‌وقت توی سورس هاردکد نکن؛ بذار توی env (مثل `MATRIX_BOT_TOKEN`).
