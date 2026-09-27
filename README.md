# Бабушкин стол — мини-приложение бабы Зои

Telegram-бот [@BabaZoya_bot](https://t.me/BabaZoya_bot) и мини-приложение с книгой «Бабушкин стол» (100 деревенских рецептов).

- Сайт мини-приложения — GitHub Pages из корня этой ветки.
- Полная книга лежит в `data/book.enc` в зашифрованном виде (AES-GCM). Ключ получает покупатель от бота после оплаты звёздами.
- Бот — `bot/bot.py`, запускается GitHub Actions (`.github/workflows/bot.yml`), работает долгим опросом.
- Секреты — только в Settings → Secrets → Actions: `BOT_TOKEN`, `BOOK_KEY`, `ADMIN_CODE`. В файлы не вставлять.
- Цена — `PRICE_STARS` в workflow и `price`/`invoice` в `config.js`.
