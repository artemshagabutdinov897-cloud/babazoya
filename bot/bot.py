# Бот бабы Зои: продажа книги «Бабушкин стол» за Telegram Stars.
# Работает долгим опросом внутри GitHub Actions (см. .github/workflows/bot.yml).
# Секреты — только в переменных окружения: BOT_TOKEN, BOOK_KEY, ADMIN_CODE.
import os, sys, json, time, base64, hashlib, subprocess, traceback
import requests
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

TOKEN = os.environ["BOT_TOKEN"]
BOOK_KEY = os.environ["BOOK_KEY"]
ADMIN_CODE = os.environ["ADMIN_CODE"].strip()
PRICE = int(os.environ.get("PRICE_STARS", "390"))
APP = os.environ.get("APP_URL", "https://artemshagabutdinov897-cloud.github.io/babazoya/")
RUN_SECONDS = int(os.environ.get("RUN_SECONDS", str(5 * 3600 + 50 * 60)))
STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")
API = f"https://api.telegram.org/bot{TOKEN}/"
S = requests.Session()


def tg(method, **params):
    for attempt in range(5):
        try:
            r = S.post(API + method, json=params, timeout=70)
            d = r.json()
            if d.get("ok"):
                return d["result"]
            if d.get("error_code") == 429:
                time.sleep(d.get("parameters", {}).get("retry_after", 3)); continue
            print("TG error", method, d.get("description"), flush=True)
            return None
        except Exception as e:
            print("TG exception", method, e, flush=True); time.sleep(3)
    return None


# ---------- состояние (публичный репозиторий: ничего личного в открытом виде) ----------
_aes = AESGCM(hashlib.sha256(("state:" + BOOK_KEY).encode()).digest())

def enc(s):
    iv = os.urandom(12); return base64.b64encode(iv + _aes.encrypt(iv, s.encode(), None)).decode()

def dec(s):
    b = base64.b64decode(s); return _aes.decrypt(b[:12], b[12:], None).decode()

def load_state():
    try:
        return json.load(open(STATE_PATH))
    except Exception:
        return {}

def save_state(st, msg="bot: state"):
    json.dump(st, open(STATE_PATH, "w"), ensure_ascii=False, indent=1)
    try:
        cwd = os.path.dirname(STATE_PATH)
        subprocess.run(["git", "add", STATE_PATH], cwd=cwd, check=True)
        if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=cwd).returncode != 0:
            subprocess.run(["git", "commit", "-m", msg], cwd=cwd, check=True)
            subprocess.run(["git", "pull", "--rebase", "-q"], cwd=cwd)
            subprocess.run(["git", "push", "-q"], cwd=cwd)
    except Exception as e:
        print("git save failed", e, flush=True)

ST = load_state()

def admin_id():
    try:
        return int(dec(ST["admin"])) if ST.get("admin") else None
    except Exception:
        return None


# ---------- тексты ----------
HELLO = ("Здравствуй, милок! Я баба Зоя.\n\n"
         "Всю жизнь кормлю людей простой деревенской едой — такой, после которой в животе легко, а не тяжело. "
         "Собрала всё в одну книжку: «Бабушкин стол», 100 рецептов — квашеная капуста, хлеб на закваске, кисели, "
         "каши, щи, мёд с пасеки и праздничный стол без тяжести.\n\n"
         "Семь рецептов открыла тебе даром — жми «Открыть книжку» и выбирай. Понравится — открою всю.")
THANKS = ("Спасибо, милок! Книжка твоя — насовсем.\n\n"
          "Нажми «Открыть всю книжку» — откроются все 100 рецептов, правила, меню на неделю и таблицы. "
          "Дальше она будет открываться сама, через кнопку «Книжка» внизу чата.")
HELP = ("Как всё устроено:\n\n"
        "• «Книжка» внизу чата — открывает приложение с рецептами.\n"
        "• Семь рецептов открыты всем, остальные — после покупки.\n"
        f"• Покупка — {PRICE} ⭐ (звёзды Telegram), один раз и навсегда.\n"
        "• Купил, а книжка закрыта? Напиши /book — пришлю ключ и PDF заново.\n"
        "• Рецепты — домашняя еда, а не лечение. Если есть болезни желудка, аллергия на мёд, беременность — посоветуйся с врачом.")

def kb_open(url=APP, text="Открыть книжку"):
    return {"inline_keyboard": [[{"text": text, "web_app": {"url": url}}]]}

def kb_start():
    return {"inline_keyboard": [
        [{"text": "Открыть книжку", "web_app": {"url": APP}}],
        [{"text": f"Вся книга — {PRICE} ⭐", "callback_data": "buy"}]]}


# ---------- покупки ----------
def send_invoice(chat):
    tg("sendInvoice", chat_id=chat, title="Бабушкин стол — 100 рецептов",
       description="Вся книга бабы Зои: 100 деревенских рецептов для лёгкого живота, правила, меню на неделю, "
                   "календарь заготовок. Откроется в приложении, PDF — в чат.",
       payload="book-v1", currency="XTR", prices=[{"label": "Книга", "amount": PRICE}],
       photo_url=APP + "img/cover.jpg", photo_width=860, photo_height=1075)

def deliver(chat, first=True):
    tg("sendMessage", chat_id=chat, text=THANKS if first else "Вот твоя книжка, милок. Жми — и все рецепты откроются.",
       reply_markup=kb_open(APP + "?k=" + BOOK_KEY, "Открыть всю книжку"))
    if ST.get("pdf"):
        tg("sendDocument", chat_id=chat, document=ST["pdf"],
           caption="А это та же книжка в PDF — распечатать или держать в телефоне. 132 страницы.")
    else:
        tg("sendMessage", chat_id=chat, text="PDF-версию пришлю чуть позже — внучка как раз её доделывает.")
        a = admin_id()
        if a: tg("sendMessage", chat_id=a, text=f"Покупатель {chat} ждёт PDF — загрузи книгу боту с подписью-кодом.")

def has_paid(uid):
    got, back, off = 0, 0, 0
    while True:
        res = tg("getStarTransactions", offset=off, limit=100)
        tr = (res or {}).get("transactions", [])
        for t in tr:
            src, rcv = t.get("source") or {}, t.get("receiver") or {}
            if src.get("type") == "user" and (src.get("user") or {}).get("id") == uid:
                got += 1
            if rcv.get("type") == "user" and (rcv.get("user") or {}).get("id") == uid:
                back += 1
        if len(tr) < 100:
            break
        off += 100
    return got > back


# ---------- обработка ----------
def on_message(m):
    chat = m["chat"]["id"]
    if m["chat"].get("type") != "private":
        return
    text = (m.get("text") or m.get("caption") or "").strip()

    if m.get("successful_payment"):
        ST["sales"] = ST.get("sales", 0) + 1
        deliver(chat)
        a = admin_id()
        if a and a != chat:
            u = m.get("from", {})
            tg("sendMessage", chat_id=a, text=f"Продажа! {u.get('first_name', '')} купил книгу за {m['successful_payment']['total_amount']} ⭐. Всего продаж: {ST['sales']}")
        save_state(ST, "bot: sale")
        return

    if m.get("document") and text == ADMIN_CODE:
        ST["pdf"] = m["document"]["file_id"]; ST["admin"] = enc(str(chat))
        save_state(ST, "bot: pdf updated")
        tg("sendMessage", chat_id=chat, text="Готово: PDF сохранила, буду отправлять покупателям. Уведомления о продажах — сюда.")
        return
    if text == "/admin " + ADMIN_CODE or text == ADMIN_CODE:
        ST["admin"] = enc(str(chat)); save_state(ST, "bot: admin")
        tg("sendMessage", chat_id=chat, text=f"Ты админ. Продаж: {ST.get('sales', 0)}. PDF: {'есть' if ST.get('pdf') else 'нет — пришли файл с подписью-кодом'}.")
        return

    if text.startswith("/start"):
        arg = text[6:].strip()
        if arg == "buy":
            send_invoice(chat); return
        if arg == "book":
            text = "/book"
        else:
            if not tg("sendPhoto", chat_id=chat, photo=APP + "img/cover.jpg", caption=HELLO, reply_markup=kb_start()):
                tg("sendMessage", chat_id=chat, text=HELLO, reply_markup=kb_start())
            return
    if text.startswith("/book"):
        uid = m.get("from", {}).get("id")
        if uid and has_paid(uid):
            deliver(chat, first=False)
        else:
            tg("sendMessage", chat_id=chat, text="Покупку не нашла, милок. Если платил — напиши сюда, разберусь. А купить можно тут:",
               reply_markup={"inline_keyboard": [[{"text": f"Вся книга — {PRICE} ⭐", "callback_data": "buy"}]]})
        return
    if text.startswith("/buy"):
        send_invoice(chat); return
    if text.startswith("/help"):
        tg("sendMessage", chat_id=chat, text=HELP, reply_markup=kb_open()); return

    # всё остальное — вопрос или отзыв: передаём админу
    a = admin_id()
    if a and a != chat and text:
        u = m.get("from", {})
        tg("sendMessage", chat_id=a, text=f"Сообщение от {u.get('first_name', '')} (@{u.get('username', '-')}, id {chat}):\n\n{text[:3500]}")
    tg("sendMessage", chat_id=chat, text="Спасибо, милок, прочитаю. А рецепты — вот тут:", reply_markup=kb_open())


def on_update(u):
    if "pre_checkout_query" in u:
        q = u["pre_checkout_query"]
        ok = q.get("invoice_payload") == "book-v1" and q.get("currency") == "XTR"
        tg("answerPreCheckoutQuery", pre_checkout_query_id=q["id"], ok=ok,
           **({} if ok else {"error_message": "Что-то не так со счётом, попробуй ещё раз из бота."}))
    elif "callback_query" in u:
        c = u["callback_query"]
        tg("answerCallbackQuery", callback_query_id=c["id"])
        if c.get("data") == "buy" and c.get("message"):
            send_invoice(c["message"]["chat"]["id"])
    elif "message" in u:
        on_message(u["message"])


def main():
    deadline = time.time() + RUN_SECONDS
    offset = None
    print("bot started", flush=True)
    while time.time() < deadline:
        left = int(deadline - time.time())
        ups = tg("getUpdates", timeout=max(1, min(50, left)), offset=offset,
                 allowed_updates=["message", "callback_query", "pre_checkout_query"])
        for u in ups or []:
            offset = u["update_id"] + 1
            try:
                on_update(u)
            except Exception:
                traceback.print_exc()
    if offset:
        tg("getUpdates", offset=offset, timeout=0)  # подтвердить обработанное
    # раз в месяц отметиться, чтобы GitHub не выключил расписание
    if time.time() - ST.get("alive", 0) > 25 * 86400:
        ST["alive"] = int(time.time()); save_state(ST, "bot: heartbeat")
    print("bot finished", flush=True)


if __name__ == "__main__":
    main()
