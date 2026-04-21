# Telegram setup — 3 minutes

This gets you a private bot that pushes triage alerts to your phone.

## 1. Create the bot

1. Open Telegram and search for `@BotFather`. Start a chat with it.
2. Send `/newbot`.
3. Give it a display name when asked (e.g. *Layer-0 Triage*).
4. Give it a username ending in `bot` (e.g. `my_layer0_triage_bot`). Must be globally unique.
5. BotFather replies with a token that looks like `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`.
6. Copy that token — this is your **`TELEGRAM_BOT_TOKEN`**.

## 2. Start a chat with your bot

1. In BotFather's reply, tap the `t.me/your_bot_username` link. Telegram opens a chat with your new bot.
2. Tap **Start** (or send `/start`).
3. Send any message — just the word "hi" works. This creates the chat record.

## 3. Get your chat ID

Open this URL in a browser, replacing `<TOKEN>` with the token from step 1:

```
https://api.telegram.org/bot<TOKEN>/getUpdates
```

You'll see a JSON response. Find the `"chat"` object and copy the value of `"id"`:

```json
{
  "message": {
    "chat": {
      "id": 123456789,        <-- this number is your TELEGRAM_CHAT_ID
      "first_name": "Basil",
      ...
    }
  }
}
```

This is your **`TELEGRAM_CHAT_ID`**. It's a positive integer for a direct chat with you.

## 4. Test

Add both values to your local `.env` file (or GitHub repo secrets) and run:

```bash
python -m src.main test
```

You should receive a test alert within a few seconds. If not, the most common issues are:

- **Wrong token format** — must include the `:` between the numeric prefix and the alphanumeric suffix.
- **Chat doesn't exist yet** — send any message to your bot first, then retry `getUpdates`.
- **Empty `getUpdates` response** — Telegram only keeps updates for 24 hours. If you created the bot days ago and never messaged it, send it a message now and re-fetch.

## Privacy note

The bot can only message users who have messaged it first, and tokens grant full bot control — don't share them or commit them to public repos. Store in `.env` (gitignored) for local use, or in GitHub repo secrets for the Actions workflows.
