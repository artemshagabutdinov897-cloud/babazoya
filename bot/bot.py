# Бот бабы Зои v2: книга, дожим, подарок, отзывы, клуб по подписке, ответы бабы Зои (ИИ).
# Работает долгим опросом в GitHub Actions. Секреты — только в переменных окружения.
import os, json, time, base64, hashlib, random, re, signal, traceback, datetime, collections, html
import requests, uuid
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

TOKEN = os.environ["BOT_TOKEN"]
BOOK_KEY = os.environ["BOOK_KEY"]
ADMIN_CODE = os.environ["ADMIN_CODE"].strip()
CLUB_KEY = os.environ.get("CLUB_KEY", "")
AI_KEY = os.environ.get("BRATUHA_API_KEY", "")
AI_MODEL = os.environ.get("AI_MODEL", "gemini-3.8-flash")
GH_TOKEN = os.environ.get("GH_TOKEN", "")
REPO = os.environ.get("GITHUB_REPOSITORY", "")
PRICE = int(os.environ.get("PRICE_STARS", "600"))
PROMO = int(os.environ.get("PROMO_STARS", "450"))
CLUB_PRICE = int(os.environ.get("CLUB_STARS", "100"))
YK = os.environ.get("YK_TOKEN", "")
RUB = int(os.environ.get("PRICE_RUB", "1300"))
RUB_PROMO = int(os.environ.get("PROMO_RUB", "990"))
RUB_OLD = int(os.environ.get("OLD_RUB", "2600"))     # зачёркнутая цена — показываем только в момент оплаты
YKS = os.environ.get("YK_SECRET", "").strip()          # секретный ключ ЮKassa (API) — для СБП
YK_SHOP = os.environ.get("YK_SHOP_ID", "1476727").strip()
BOT_NAME = os.environ.get("BOT_NAME", "BabaZoya_bot")
APP = os.environ.get("APP_URL", "https://artemshagabutdinov897-cloud.github.io/babazoya/")
RUN_SECONDS = int(os.environ.get("RUN_SECONDS", str(5 * 3600 + 50 * 60)))
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MSK = datetime.timezone(datetime.timedelta(hours=3))
CLUB_START = datetime.datetime(2026, 9, 28, tzinfo=MSK)
DAY = 86400
AI_USER_DAY, AI_GLOBAL_DAY = 20, 500
API = f"https://api.telegram.org/bot{TOKEN}/"
S = requests.Session()


def tg(method, **params):
    for _ in range(5):
        try:
            d = S.post(API + method, json=params, timeout=70).json()
            if d.get("ok"):
                return d["result"]
            if d.get("error_code") == 429:
                time.sleep(d.get("parameters", {}).get("retry_after", 3)); continue
            print("TG error", method, d.get("description"), flush=True)
            if d.get("error_code") == 403 and "chat_id" in params:
                u = ST["users"].get(str(params["chat_id"]))
                if u is not None: u["blocked"] = 1; mark()
            return None
        except Exception as e:
            print("TG exception", method, e, flush=True); time.sleep(3)
    return None


# ---------- шифрование и состояние (ветка bot-state, всё зашифровано) ----------
_KEY = hashlib.sha256(("state:" + BOOK_KEY).encode()).digest()

def _enc(b, key=_KEY):
    iv = os.urandom(12); return base64.b64encode(iv + AESGCM(key).encrypt(iv, b, None)).decode()

def _dec(s, key=_KEY):
    b = base64.b64decode(s); return AESGCM(key).decrypt(b[:12], b[12:], None)

def gh(method, path, **kw):
    return requests.request(method, f"https://api.github.com/repos/{REPO}{path}",
                            headers={"Authorization": f"Bearer {GH_TOKEN}", "Accept": "application/vnd.github+json"},
                            timeout=30, **kw)

DEFAULT = {"v": 2, "pdf": None, "admin": None, "users": {}, "gifts": {}, "stars": {}, "sales": {},
           "ai_day": "", "ai_count": 0, "alive": 0}
ST, SHA, DIRTY, LAST_SAVE = None, None, False, 0
LOCAL = os.path.join(HERE, "state.local.json")

def mark():
    global DIRTY
    DIRTY = True

def load_state():
    global ST, SHA
    st = None
    if GH_TOKEN and REPO:
        r = gh("GET", "/contents/state.enc", params={"ref": "bot-state"})
        if r.status_code == 200:
            j = r.json(); SHA = j["sha"]
            st = json.loads(_dec(base64.b64decode(j["content"]).decode()))
    elif os.path.exists(LOCAL):
        st = json.load(open(LOCAL))
    if st is None:  # перенос со старой версии
        st = json.loads(json.dumps(DEFAULT))
        try:
            old = json.load(open(os.path.join(HERE, "state.json")))
            st["pdf"] = old.get("pdf")
            if old.get("admin"): st["admin"] = int(_dec(old["admin"]).decode())
            st["sales"]["book"] = old.get("sales", 0)
        except Exception as e:
            print("no old state", e, flush=True)
    for k, v in DEFAULT.items():
        st.setdefault(k, json.loads(json.dumps(v)))
    ST = st

def save_state(force=False):
    global SHA, DIRTY, LAST_SAVE
    if not (DIRTY or force):
        return
    data = _enc(json.dumps(ST, ensure_ascii=False).encode())
    if not (GH_TOKEN and REPO):
        json.dump(ST, open(LOCAL, "w"), ensure_ascii=False); DIRTY = False; LAST_SAVE = time.time(); return
    for attempt in range(3):
        if SHA is None:
            if gh("GET", "/git/ref/heads/bot-state").status_code == 404:
                main = gh("GET", "/git/ref/heads/main").json()["object"]["sha"]
                gh("POST", "/git/refs", json={"ref": "refs/heads/bot-state", "sha": main})
            else:
                r = gh("GET", "/contents/state.enc", params={"ref": "bot-state"})
                if r.status_code == 200: SHA = r.json()["sha"]
        body = {"message": "bot: state", "content": base64.b64encode(data.encode()).decode(), "branch": "bot-state"}
        if SHA: body["sha"] = SHA
        r = gh("PUT", "/contents/state.enc", json=body)
        if r.status_code in (200, 201):
            SHA = r.json()["content"]["sha"]; DIRTY = False; LAST_SAVE = time.time(); return
        print("state save failed", r.status_code, r.text[:200], flush=True)
        SHA = None; time.sleep(2)

def write_status():
    if not (GH_TOKEN and REPO): return
    save_state(force=True)
    body = {"message": "bot: status", "branch": "bot-state", "content": base64.b64encode(json.dumps({
        "started": datetime.datetime.now(MSK).isoformat(), "recipes": len(IDX), "club_letters": len(CLUB),
        "ai": bool(AI_KEY), "sbp": bool(YKS), "card": bool(YK), "users": len(ST["users"]), "pdf": bool(ST.get("pdf")), "admin": bool(ST.get("admin"))}).encode()).decode()}
    r = gh("GET", "/contents/status.json", params={"ref": "bot-state"})
    if r.status_code == 200: body["sha"] = r.json()["sha"]
    gh("PUT", "/contents/status.json", json=body)

def heartbeat():
    # раз в месяц коммит в main, чтобы GitHub не выключил расписание
    if time.time() - ST.get("alive", 0) < 25 * DAY or not (GH_TOKEN and REPO):
        return
    path = "/contents/bot/alive.txt"
    r = gh("GET", path); sha = r.json().get("sha") if r.status_code == 200 else None
    body = {"message": "bot: heartbeat", "content": base64.b64encode(str(int(time.time())).encode()).decode()}
    if sha: body["sha"] = sha
    if gh("PUT", path, json=body).status_code in (200, 201):
        ST["alive"] = int(time.time()); mark()

def user(uid, src=None):
    k = str(uid); u = ST["users"].get(k)
    if u is None:
        u = ST["users"][k] = {"src": src or "direct", "t0": int(time.time())}; mark()
    return u

def admin_id():
    return ST.get("admin")

def to_admin(text, **kw):
    a = admin_id()
    if a: tg("sendMessage", chat_id=a, text=text, **kw)

def now():
    return int(time.time())

def daytime():
    h = datetime.datetime.now(MSK).hour
    return 9 <= h < 21


# ---------- книга (для ответов бабы Зои и подарочного рецепта) ----------
def load_book():
    try:
        raw = open(os.path.join(ROOT, "data", "book.enc"), "rb").read()
        k = base64.urlsafe_b64decode(BOOK_KEY + "=" * (-len(BOOK_KEY) % 4))
        return json.loads(AESGCM(k).decrypt(raw[:12], raw[12:], None))
    except Exception as e:
        print("book load failed", e, flush=True); return {"recipes": []}

BOOK = {"recipes": []}
IDX = []

STOP_W = {"что", "чего", "приг", "сдел", "можн", "есть", "реце", "хочу", "како", "как", "надо", "нужн", "мне", "меня",
          "дома", "оста", "пожа", "подс", "посо", "бабу", "баба", "зоя", "прив", "здра", "спас", "будь", "свар",
          "испе", "пожа", "блюд", "вкус", "прос", "быст", "очен", "може", "подс", "есть", "еще", "ещё", "так", "это"}

def words(s):
    s = s.lower().replace("ё", "е")
    return [w[:4] for w in re.findall(r"[а-яa-z]{3,}", s) if w[:4] not in STOP_W]

def build_index():
    global IDX
    IDX = []
    for r in BOOK.get("recipes", []):
        ing = " ".join(r.get("ing") or [])
        IDX.append((r, set(words(r.get("title", ""))), set(words(ing))))

def find_recipes(q, k=3):
    qs = set(words(q)); scored = []
    for r, t, i in IDX:
        s = 2 * len(qs & t) + len(qs & i)
        if s: scored.append((s, r))
    scored.sort(key=lambda x: -x[0])
    return [r for _, r in scored[:k]]

def recipe_text(r, full=True):
    out = [f"№{r['n']}. {r['title']}", f"Время: {r.get('time', '')}. Выход: {r.get('yield', '')}."]
    if full:
        out.append("Что нужно: " + "; ".join(r.get("ing") or []))
        out.append("Как делать: " + " ".join(f"{i + 1}) {s}" for i, s in enumerate(r.get("steps") or [])))
        if r.get("tip"): out.append("Совет: " + r["tip"])
        if r.get("warn") and r["warn"] != "None": out.append("Осторожно: " + r["warn"])
    return "\n".join(out)

def teaser(r):
    e = html.escape; steps = r.get("steps") or []
    show = max(1, min(2, len(steps) - 2)); hidden = len(steps) - show
    lines = ["Есть у меня для тебя рецепт, милок 🎁", "", f"<b>{e(r['title'])}</b> (в книжке это №{r['n']})",
             f"<i>{e(r.get('intro', ''))}</i>", "", "<b>Что нужно:</b>"] + [f"— {e(x)}" for x in r.get("ing") or []]
    lines += ["", "<b>Как делаю:</b>"] + [f"{i + 1}. {e(x)}" for i, x in enumerate(steps[:show])]
    lines += ["", f"🔒 Дальше ещё {hidden} {'шаг' if hidden == 1 else 'шага' if hidden < 5 else 'шагов'} и мой совет — в полной книжке. "
                  "Там все 100 рецептов, а спрашивать меня можно сколько хочешь."]
    return "\n".join(lines)

def recipe_card(n):
    """Фото главы + подпись с рецептом. Если рецепт длиннее подписи (1024), остаток — отдельным сообщением."""
    r = next((x for x in BOOK.get("recipes", []) if str(x["n"]) == str(n)), None)
    if not r: return None
    e = html.escape
    head = [f"<b>{e(r['title'])}</b>"]
    if r.get("intro"): head.append(f"<i>{e(r['intro'])}</i>")
    meta = " · ".join(x for x in [f"⏱ {e(r['time'])}" if r.get("time") else "", f"🫙 {e(r['yield'])}" if r.get("yield") else ""] if x)
    if meta: head += ["", meta]
    body = ["<b>Что нужно</b>"] + [f"• {e(x)}" for x in r.get("ing") or []]
    body += ["", "<b>Как делаю</b>"] + [f"{i + 1}. {e(x)}" for i, x in enumerate(r.get("steps") or [])]
    if r.get("tip"): body += ["", f"<blockquote>💡 <b>Совет бабы Зои:</b> {e(r['tip'])}</blockquote>"]
    if r.get("warn") and r["warn"] != "None": body += [f"⚠️ {e(r['warn'])}"]
    photo = APP + f"img/ch{r.get('ch', 1)}.jpg"
    full = "\n".join(head + [""] + body)
    if len(full) <= 1000: return photo, full, None
    return photo, "\n".join(head), "\n".join(body)

def send_card(chat, n, markup=None):
    c = recipe_card(n)
    if not c: return False
    photo, cap, rest = c
    if rest is None:
        ok = tg("sendPhoto", chat_id=chat, photo=photo, caption=cap, parse_mode="HTML", reply_markup=markup)
        if not ok: tg("sendMessage", chat_id=chat, text=cap, parse_mode="HTML", reply_markup=markup)
    else:
        tg("sendPhoto", chat_id=chat, photo=photo, caption=cap, parse_mode="HTML")
        tg("sendMessage", chat_id=chat, text=rest, parse_mode="HTML", reply_markup=markup)
    return True

def recipe_message(n):
    r = next((x for x in BOOK.get("recipes", []) if str(x["n"]) == str(n)), None)
    if not r: return None
    e = html.escape
    lines = [f"<b>{e(r['title'])}</b>", f"<i>{e(r.get('intro', ''))}</i>", "", "<b>Что нужно:</b>"]
    lines += [f"— {e(x)}" for x in r.get("ing") or []]
    lines += ["", "<b>Как делаю:</b>"] + [f"{i + 1}. {e(s)}" for i, s in enumerate(r.get("steps") or [])]
    if r.get("tip"): lines += ["", f"<b>Совет бабы Зои:</b> {e(r['tip'])}"]
    return "\n".join(lines)


# ---------- клуб ----------
CLUB = []
CLUB_LINK = None

def load_club():
    global CLUB
    if not CLUB_KEY: return
    try:
        raw = open(os.path.join(HERE, "club.enc")).read()
        k = base64.urlsafe_b64decode(CLUB_KEY + "=" * (-len(CLUB_KEY) % 4))
        CLUB = json.loads(_dec(raw, k))
    except Exception as e:
        print("club load failed", e, flush=True)

def released():
    if not CLUB: return -1
    weeks = (datetime.datetime.now(MSK) - CLUB_START).days // 7
    return max(0, min(len(CLUB) - 1, weeks))

def club_link():
    global CLUB_LINK
    if CLUB_LINK is None and CLUB:
        CLUB_LINK = tg("createInvoiceLink", title="Клуб бабы Зои",
                       description="Каждую неделю — новое письмо от бабы Зои: рецепт, которого нет в книжке, заготовки по сезону и истории с пасеки.",
                       payload="club-v1", currency="XTR", prices=[{"label": "Месяц", "amount": CLUB_PRICE}],
                       subscription_period=2592000)
    return CLUB_LINK

def in_club(u):
    return u.get("club", 0) > now()

def send_letter(chat, i):
    L = CLUB[i]
    tg("sendMessage", chat_id=chat, text=f"✉️ <b>{L['title']}</b>\n\n{L['text']}", parse_mode="HTML")


# ---------- тексты и кнопки ----------
HELLO = ("<b>Здравствуй, милок!</b> 👋\n"
         "Я баба Зоя. Всю жизнь кормлю людей простой деревенской едой, после которой в животе легко, а не тяжело.\n\n"
         "Для начала дарю тебе <b>7 рецептов</b>: квашеную капусту, огурцы за сутки, овсяный кисель, медовую воду.\n\n"
         "А если напишешь, какой продукт у тебя есть, подберу, что из него приготовить.")
HELLO_PLAIN = "Здравствуй, милок! 👋"
THANKS = ("Спасибо, милок! Книжка твоя — насовсем.\n\n"
          "Нажми «Открыть всю книжку» — откроются все 100 рецептов, правила, меню на неделю и таблицы. "
          "Дальше она будет открываться сама, через кнопку «Книжка» внизу чата.\n\n"
          "И спрашивай меня прямо здесь: напиши, что есть в холодильнике, — подскажу, что приготовить.")

def kb(*rows):
    return {"inline_keyboard": [list(r) for r in rows]}

B_OPEN = {"text": "Открыть книжку", "web_app": {"url": APP}}
def B_BUY(): return {"text": "📖 Купить всю книжку", "callback_data": "buy_choice" if (YK or YKS) else "buy"}
def buy_rows():
    return [[B_BUY()]]
def money(amount, cur):
    return f"{amount // 100} ₽" if cur == "RUB" else f"{amount} ⭐"
B_GIFT = {"text": "🎁 Подарить книжку", "callback_data": "gift"}
B_CLUB = {"text": "✉️ Клуб бабы Зои", "callback_data": "club"}
B_FREE = {"text": "🎁 Забрать 7 рецептов", "callback_data": "free"}
B_TEST = {"text": "🥣 Тест: какой у тебя живот", "callback_data": "test"}
M_BOOK, M_FREE, M_ASK = "📖 Книжка", "🎁 Рецепты", "💬 Спросить"
def menu_kb():
    return {"keyboard": [[{"text": M_BOOK, "web_app": {"url": APP}}, {"text": M_FREE}, {"text": M_ASK}]],
            "resize_keyboard": True, "is_persistent": True}
EMO = {1: "🥬", 4: "🍎", 7: "🥒", 8: "🟣", 11: "🥕", 41: "🍯", 56: "🥣"}
SHORT = {1: "Капуста", 4: "Мочёные яблоки", 7: "Огурцы", 8: "Свекольный квас", 11: "Морковь", 41: "Медовая вода", 56: "Овсяный кисель"}
FREE = [1, 7, 8, 4, 11, 41, 56]
# рецепты-подарки по кодовым словам из Instagram (ссылка вида ?start=r22 или ?start=r21_22)
LEAD = {4, 7, 8, 21, 22, 41, 42, 56, 57, 64}

def send_lead(chat, uid, nums):
    u = user(uid); got = set(u.get("lead", []))
    tg("sendMessage", chat_id=chat, text="Здравствуй, милок! Я баба Зоя 👋 Обещала рецепт, держи.", reply_markup=menu_kb())
    for n in nums:
        if send_card(chat, n): got.add(n)
    u["lead"] = sorted(got); mark()
    tg("sendMessage", chat_id=chat, reply_markup=kb([B_FREE], *buy_rows(), [B_OPEN]),
       text=("Это один рецепт из моей книжки «Бабушкин стол». Там их сто — капуста, хлеб, кисели, каши, мёд с пасеки.\n\n"
             "Ещё семь дарю просто так — жми «7 рецептов даром». А напишешь, какой продукт у тебя есть, — подберу, что приготовить."))

def free_menu(chat):
    btns = [{"text": f"{EMO.get(n, '🍽')} {SHORT.get(n, '')}".strip(), "callback_data": f"fr_{n}"} for n in FREE]
    rows = [btns[i:i + 2] for i in range(0, len(btns), 2)]
    tg("sendMessage", chat_id=chat, reply_markup=kb(*rows), text="Выбирай, милок, с чего начнём 👇")

def send_free(chat, uid, n):
    u = user(uid); got = set(u.get("free", [])); got.add(n); u["free"] = sorted(got)
    u.setdefault("tf", now()); mark()
    nxt = next((x for x in FREE if x not in got), None)
    rows = ([[{"text": "➡️ Следующий рецепт", "callback_data": f"fr_{nxt}"}]] if nxt else []) + \
           [[{"text": "📖 Вся книжка: 100 рецептов", "callback_data": "card"}]]
    send_card(chat, n, kb(*rows))

def book_card(chat, kind="book"):
    old, new = RUB_OLD, (RUB_PROMO if kind == "promo" else RUB)
    cap = ("<b>«Бабушкин стол»: 100 рецептов</b>\n\n"
           "🥬 Живые заготовки\n🔥 Печка: хлеб и пироги\n🍯 Пасека: мёд и перга\n🥣 Каши, кисели, взвары\n"
           "🍲 Супы и простая еда\n🎄 Праздничный стол без тяжести\n\n"
           "+ меню на неделю, таблицы, и спрашивать меня можно сколько хочешь.\n\n"
           f"<s>{old} ₽</s>  <b>{new} ₽</b>, один раз и навсегда")
    rows = []
    if YKS: rows.append([{"text": f"⚡ Оплатить {new} ₽ по СБП", "callback_data": f"{kind}_sbp"}])
    if YK: rows.append([{"text": "💳 Картой", "callback_data": f"{kind}_rub"}])
    rows.append([{"text": "⭐ Звёздами Telegram", "callback_data": f"{kind}_xtr"}])
    if kind == "book": rows.append([B_GIFT])
    if not tg("sendPhoto", chat_id=chat, photo=APP + "img/cover.jpg", caption=cap, parse_mode="HTML", reply_markup=kb(*rows)):
        tg("sendMessage", chat_id=chat, text=cap, parse_mode="HTML", reply_markup=kb(*rows))

HELLO_NOTE = os.path.join(ROOT, "img", "hello.mp4")

def greet(chat):
    note = ST.get("hello_note")
    if note:
        ok = tg("sendVideoNote", chat_id=chat, video_note=note, reply_markup=menu_kb())
    elif os.path.exists(HELLO_NOTE):
        ok = None
        try:
            r = S.post(API + "sendVideoNote", data={"chat_id": chat, "length": 640, "reply_markup": json.dumps(menu_kb())},
                       files={"video_note": ("hello.mp4", open(HELLO_NOTE, "rb"), "video/mp4")}, timeout=120).json()
            if r.get("ok"):
                ok = r["result"]; ST["hello_note"] = r["result"]["video_note"]["file_id"]; mark()
        except Exception as e:
            print("video note upload failed", e, flush=True)
    else:
        ok = None
    if not ok:
        tg("sendMessage", chat_id=chat, text=HELLO_PLAIN, reply_markup=menu_kb())
    if not tg("sendPhoto", chat_id=chat, photo=APP + "img/mockup.jpg", caption=HELLO, parse_mode="HTML", reply_markup=start_kb()):
        tg("sendMessage", chat_id=chat, text=HELLO, parse_mode="HTML", reply_markup=start_kb())

def start_kb():
    return kb([B_FREE], [B_TEST])


# ---------- оплата ----------
def invoice(chat, kind, cur="XTR"):
    if cur == "RUB" and not YK: cur = "XTR"
    title, desc, payload, amount = {
        "book": ("Бабушкин стол — 100 рецептов", "Вся книга бабы Зои: 100 деревенских рецептов для лёгкого живота, правила, меню на неделю. В приложении и PDF в чат.", "book-v1", PRICE),
        "promo": ("Бабушкин стол — со скидкой", f"Вся книга бабы Зои за {PROMO} ⭐ вместо {PRICE}. Скидка действует сутки.", "promo-v1", PROMO),
        "gift": ("Книжка «Бабушкин стол» в подарок", "Пришлю тебе открытку со ссылкой — перешлёшь её тому, кому даришь. Открыть подарок можно один раз.", "gift-v1", PRICE),
    }[kind]
    extra = {}
    if cur == "RUB":
        amount = (RUB_PROMO if kind == "promo" else RUB) * 100
        desc = desc.replace(f"за {PROMO} ⭐ вместо {PRICE}", f"за {RUB_PROMO} ₽ вместо {RUB}")
        extra = {"provider_token": YK}
    tg("sendInvoice", chat_id=chat, title=title, description=desc, payload=payload, currency=cur,
       prices=[{"label": "Книга", "amount": amount}], photo_url=APP + "img/mockup.jpg", photo_width=1080, photo_height=1935, **extra)

def pay_choice(chat, kind, text):
    if not (YK or YKS): return invoice(chat, kind)
    if kind in ("book", "promo"): return book_card(chat, kind)
    rows = []
    if YKS: rows.append([{"text": "⚡ СБП — через приложение банка", "callback_data": f"{kind}_sbp"}])
    if YK: rows.append([{"text": "💳 Картой", "callback_data": f"{kind}_rub"}])
    rows.append([{"text": "⭐ Звёздами Telegram", "callback_data": f"{kind}_xtr"}])
    tg("sendMessage", chat_id=chat, text=text, reply_markup=kb(*rows))


# ---------- СБП через API ЮKassa: ссылка на страницу оплаты, бот сам проверяет статус ----------
YK_API = "https://api.yookassa.ru/v3/payments"
SBP_DESC = {"book": "Книга «Бабушкин стол» — 100 рецептов", "promo": "Книга «Бабушкин стол» со скидкой",
            "gift": "Книга «Бабушкин стол» в подарок", "check": "Проверка оплаты"}

def yk(method, path="", **kw):
    try:
        r = requests.request(method, YK_API + path, auth=(YK_SHOP, YKS), timeout=30, **kw)
        j = r.json()
        if r.status_code >= 300: print("YK error", r.status_code, j.get("code"), j.get("description"), flush=True)
        return r.status_code, j
    except Exception as e:
        print("YK exception", e, flush=True); return 0, {}

def sbp_pay(chat, uid, kind):
    if not YKS: return pay_choice(chat, kind if kind != "check" else "book", "Как удобнее заплатить, милок?")
    rub = 100 if kind == "check" else RUB_PROMO if kind == "promo" else RUB
    body = {"amount": {"value": f"{rub}.00", "currency": "RUB"}, "capture": True,
            "confirmation": {"type": "redirect", "return_url": f"https://t.me/{BOT_NAME}"},
            "description": SBP_DESC[kind], "metadata": {"uid": str(uid), "chat": str(chat), "kind": kind},
            "payment_method_data": {"type": "sbp"}}
    code, j = yk("POST", json=body, headers={"Idempotence-Key": str(uuid.uuid4())})
    if code >= 300 or not j.get("confirmation"):
        body.pop("payment_method_data")  # СБП не включён — пусть ЮKassa покажет все способы
        code, j = yk("POST", json=body, headers={"Idempotence-Key": str(uuid.uuid4())})
    url = (j.get("confirmation") or {}).get("confirmation_url")
    if not url:
        to_admin(f"СБП не создался: {j.get('code')} {j.get('description')}")
        return tg("sendMessage", chat_id=chat, text="Ой, милок, СБП сейчас не открылся. Попробуй картой или звёздами:",
                  reply_markup=kb([{"text": "💳 Картой", "callback_data": f"{kind}_rub"}] if YK else [B_FREE],
                                  [{"text": "⭐ Звёздами Telegram", "callback_data": f"{kind}_xtr"}]))
    ST.setdefault("yk", {})[j["id"]] = {"uid": uid, "chat": chat, "kind": kind, "t": now()}; mark(); save_state()
    old = f"<s>{RUB_OLD} ₽</s> " if kind != "check" else ""
    tg("sendMessage", chat_id=chat, parse_mode="HTML", text=(f"Оплата по СБП — {old}<b>{rub} ₽</b>.\n\nЖми кнопку: откроется страница оплаты, выбери свой банк — "
                                          "он сам откроется, останется подтвердить. Как деньги придут, я сразу пришлю книжку сюда."),
       reply_markup=kb([{"text": f"⚡ Оплатить {rub} ₽ по СБП", "url": url}],
                       [{"text": "Я оплатил(а)", "callback_data": "ykc_" + j["id"]}]))

def yk_check(pid, manual_chat=None):
    p = ST.get("yk", {}).get(pid)
    if not p: return
    code, j = yk("GET", "/" + pid)
    st = j.get("status")
    if st == "succeeded" and j.get("paid"):
        ST["yk"].pop(pid, None); mark()
        amt = int(round(float(j["amount"]["value"]) * 100))
        grant(p["chat"], p["uid"], "", p["kind"], amt, "RUB", via="sbp")
    elif st == "canceled":
        ST["yk"].pop(pid, None); mark()
        if manual_chat: tg("sendMessage", chat_id=manual_chat, text="Оплата не прошла, милок. Попробуй ещё раз — /buy")
    elif manual_chat:
        tg("sendMessage", chat_id=manual_chat, text="Пока денег не вижу, милок. Если уже подтвердил в банке — подожди минутку, книжка придёт сама.")

LAST_YK = 0
def yk_poll():
    global LAST_YK
    if not YKS or not ST.get("yk") or time.time() - LAST_YK < 15: return
    LAST_YK = time.time()
    for pid, p in list(ST["yk"].items()):
        if now() - p["t"] > 2 * 3600: ST["yk"].pop(pid, None); mark(); continue
        yk_check(pid)

def deliver(chat, text=THANKS):
    tg("sendMessage", chat_id=chat, text=text,
       reply_markup=kb([{"text": "Открыть всю книжку", "web_app": {"url": APP + "?k=" + BOOK_KEY}}]))
    if ST.get("pdf"):
        tg("sendDocument", chat_id=chat, document=ST["pdf"], caption="А это та же книжка в PDF — распечатать или держать в телефоне.")
    else:
        tg("sendMessage", chat_id=chat, text="PDF-версию пришлю чуть позже — внучка как раз её доделывает.")
        to_admin(f"Покупатель {chat} ждёт PDF — загрузи книгу боту с подписью-кодом.")

def has_paid(uid):
    u = user(uid)
    if u.get("paid"): return True
    got = back = 0; off = 0
    while True:
        tr = (tg("getStarTransactions", offset=off, limit=100) or {}).get("transactions", [])
        for t in tr:
            s, r = t.get("source") or {}, t.get("receiver") or {}
            if s.get("type") == "user" and (s.get("user") or {}).get("id") == uid: got += 1
            if r.get("type") == "user" and (r.get("user") or {}).get("id") == uid: back += 1
        if len(tr) < 100: break
        off += 100
    if got > back:
        u["paid"] = 1; u.setdefault("tp", now()); mark(); return True
    return False

def count_sale(u, kind, amount, cur="XTR"):
    ST["sales"][kind] = ST["sales"].get(kind, 0) + 1
    if cur == "RUB":
        ST.setdefault("rub", {}); ST["rub"][kind] = ST["rub"].get(kind, 0) + amount // 100
    else:
        ST["stars"][kind] = ST["stars"].get(kind, 0) + amount
    ST["sales"]["src:" + u.get("src", "direct")] = ST["sales"].get("src:" + u.get("src", "direct"), 0) + 1
    mark()

def on_payment(m):
    chat = m["chat"]["id"]; uid = m["from"]["id"]; u = user(uid); sp = m["successful_payment"]
    pl, amount, cur = sp.get("invoice_payload", ""), sp.get("total_amount", 0), sp.get("currency", "XTR")
    name = m["from"].get("first_name", "")
    if pl in ("book-v1", "promo-v1", "gift-v1", "check-v1"):
        return grant(chat, uid, name, pl[:-3], amount, cur)
    if pl == "club-v1":
        _club_payment(m, u, sp, amount, chat, name)

def grant(chat, uid, name, kind, amount, cur, via=""):
    u = user(uid); how = " по СБП" if via == "sbp" else ""
    if kind in ("book", "promo"):
        u["paid"] = 1; u["tp"] = now(); u["via"] = kind
        count_sale(u, kind, amount, cur); deliver(chat)
        to_admin(f"Продажа! {name or uid} купил книгу за {money(amount, cur)}{how} ({kind}, источник: {u.get('src')}).")
    elif kind == "gift":
        code = "".join(random.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(8))
        ST["gifts"][code] = {"by": uid, "t": now(), "to": None}; count_sale(u, "gift", amount, cur)
        link = f"https://t.me/BabaZoya_bot?start=g{code}"
        cap = ("🎁 <b>Тебе подарок!</b>\n\nКнижка «Бабушкин стол» — 100 деревенских рецептов для лёгкого живота: "
               "квашеная капуста, хлеб на закваске, кисели, каши и мёд с пасеки.\n\n"
               f"Открыть подарок: {link}\n\nС любовью, баба Зоя")
        tg("sendPhoto", chat_id=chat, photo=APP + "img/mockup.jpg", caption=cap, parse_mode="HTML",
           reply_markup=kb([{"text": "🎁 Открыть подарок", "url": link}]))
        tg("sendMessage", chat_id=chat, text="Готово, милок! Перешли открытку выше тому, кому даришь. Открыть её можно один раз — я скажу, когда откроют.")
        to_admin(f"Продажа! {name or uid} купил книгу в подарок за {money(amount, cur)}{how}.")
    elif kind == "check":
        tg("sendMessage", chat_id=chat, text=f"✅ Проверочная оплата {money(amount, cur)}{how} прошла. Оплата работает.")
        to_admin(f"Проверочная оплата {money(amount, cur)}{how} прошла (id {chat}).")
    mark(); save_state()

def _club_payment(m, u, sp, amount, chat, name):
    if True:  # клуб — только звёздами
        exp = sp.get("subscription_expiration_date") or now() + 30 * DAY
        first = not u.get("club_ever"); u["club"] = exp; u["club_ever"] = 1
        if first or not sp.get("is_recurring"):
            count_sale(u, "club", amount)
            u["cl"] = released()
            tg("sendMessage", chat_id=chat, text=("Добро пожаловать в клуб, милок! Раз в неделю буду присылать тебе письмо: "
                "рецепт, которого нет в книжке, что заготавливать по сезону и что у нас на пасеке.\n\n"
                "Все письма — по команде /club. Отменить подписку можно в любой момент в настройках Telegram."))
            if u["cl"] >= 0: send_letter(chat, u["cl"])
            to_admin(f"Новый участник клуба: {name} ({amount} ⭐/мес).")
        else:
            count_sale(u, "club_renew", amount)
    mark(); save_state()


# ---------- тест «Какой у тебя живот» ----------
TEST = [
    ("Как живот после обеда?", ["Легко, будто и не ел", "Бывает тяжесть", "Почти всегда камнем, клонит в сон"]),
    ("Квашеное ешь — капусту, огурцы, квас?", ["Каждый день", "Иногда", "Почти никогда"]),
    ("Что у тебя на завтрак?", ["Каша или что-то домашнее", "Бутерброд да кофе", "Ничего, на бегу"]),
    ("Какой хлеб ешь?", ["Свой или ржаной", "Обычный магазинный", "Батоны да выпечку"]),
    ("Как после праздников?", ["Всё хорошо", "Пару дней тяжело", "Неделю в себя прихожу"]),
]
RESULTS = [
    (3, "Живот у тебя, милок, лёгкий 🌿", "Ешь ты по-деревенски, живот и благодарит. Держи мой взвар — он к любому столу, а после праздников особенно.", [64]),
    (6, "Живот просит подмоги 🥬", "Ест живот много магазинного, а живого мало. Начни с простого — квашеной капусты к обеду. Держи мой рецепт.", [1]),
    (10, "Живот устал, милок 🍯", "Тяжёлое да на бегу — вот живот и устаёт. Начни утро с овсяного киселя, как у нас в деревне. Держи рецепт.", [56]),
]

def test_q(chat, u, i):
    q, opts = TEST[i]
    rows = [[{"text": o, "callback_data": f"tq_{i}_{j}"}] for j, o in enumerate(opts)]
    tg("sendMessage", chat_id=chat, text=f"Вопрос {i + 1} из {len(TEST)}\n\n<b>{q}</b>", parse_mode="HTML", reply_markup=kb(*rows))

def test_start(chat, u):
    u["test"] = []; mark()
    tg("sendMessage", chat_id=chat, text="Давай узнаем, какой у тебя живот, милок. Пять вопросов, отвечай как есть — я не ругаюсь 🙂")
    test_q(chat, u, 0)

def test_answer(chat, uid, u, i, j):
    ans = u.get("test", [])
    if len(ans) != i: return
    ans.append(j); u["test"] = ans; mark()
    if len(ans) < len(TEST): return test_q(chat, u, len(ans))
    score = sum(ans)
    for top, title, text, nums in RESULTS:
        if score <= top: break
    u["test_res"] = title; ST["sales"]["test"] = ST["sales"].get("test", 0) + 1; mark()
    tg("sendMessage", chat_id=chat, parse_mode="HTML",
       text=f"<b>{title}</b>\n\n{text}\n\n<i>Это не диагноз, а бабушкины наблюдения. Если живот болит всерьёз — к врачу.</i>")
    for n in nums:
        msg = recipe_message(n)
        if msg: tg("sendMessage", chat_id=chat, text=msg, parse_mode="HTML")
    tg("sendMessage", chat_id=chat, reply_markup=kb([B_FREE], *buy_rows()),
       text="А сто таких рецептов — в моей книжке «Бабушкин стол». Ещё семь дарю просто так 👇")
    to_admin(f"Тест прошёл id {uid}: {title} ({score} баллов)")


# ---------- ответы бабы Зои ----------
HIST = collections.defaultdict(lambda: collections.deque(maxlen=6))
SYSTEM = ("Ты — баба Зоя, 74-летняя деревенская бабушка из-под Рязани: русская печь, огород, пасека. Автор книжки «Бабушкин стол». "
          "Говоришь тепло, просто, по-деревенски, обращаешься «милок», без смайликов и без списков с заголовками. Отвечай коротко: до 90 слов. "
          "Помогаешь с готовкой: что приготовить из того, что есть, как сделать рецепт, как заменить продукт, как хранить заготовки. "
          "Если подходит рецепт из книжки — назови его и номер («в книжке это №57»), кратко подскажи суть. "
          "Не лечишь и не ставишь диагнозов: на вопросы о болезнях, лекарствах, беременности, диетах при заболеваниях — мягко скажи, что это к врачу, и что твои рецепты — просто еда. "
          "Мёд детям до года нельзя — напоминай, если к месту. Не выдумывай фактов о себе сверх сказанного. "
          "Если спрашивают не про еду и хозяйство — по-доброму верни разговор к кухне.")

def ai_allowed(uid):
    today = datetime.datetime.now(MSK).strftime("%Y-%m-%d")
    if ST["ai_day"] != today: ST["ai_day"], ST["ai_count"] = today, 0
    u = user(uid)
    if u.get("ai_d") != today: u["ai_d"], u["ai_n"] = today, 0
    return u["ai_n"] < AI_USER_DAY and ST["ai_count"] < AI_GLOBAL_DAY

def ai_answer(uid, text):
    ctx = find_recipes(text)
    sys = SYSTEM
    if ctx:
        sys += "\n\nРецепты из твоей книжки, которые могут подойти:\n\n" + "\n\n".join(recipe_text(r) for r in ctx)
    msgs = [{"role": "system", "content": sys}] + list(HIST[uid]) + [{"role": "user", "content": text[:1500]}]
    try:
        r = requests.post("https://bratuha.ru/api/v1/chat/completions", headers={"Authorization": "Bearer " + AI_KEY},
                          json={"model": AI_MODEL, "messages": msgs, "max_tokens": 400, "temperature": 0.7}, timeout=90)
        ans = r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print("AI failed", e, flush=True); return None
    HIST[uid].append({"role": "user", "content": text[:1500]}); HIST[uid].append({"role": "assistant", "content": ans})
    u = user(uid); u["ai_n"] = u.get("ai_n", 0) + 1; ST["ai_count"] += 1; mark()
    return ans

SUPPORT = re.compile(r"оплат|заплатил|не при(шл|ход)|не откры|верн(и|уть) деньг|возврат|ошибк|не работает|pdf", re.I)


# ---------- обработка сообщений ----------
def on_message(m):
    if m["chat"].get("type") != "private": return
    chat = m["chat"]["id"]; uid = m.get("from", {}).get("id", chat)
    text = (m.get("text") or m.get("caption") or "").strip()
    if m.get("successful_payment"): return on_payment(m)
    u = user(uid)

    # админ: загрузка PDF и регистрация
    if m.get("document") and text == ADMIN_CODE:
        ST["pdf"] = m["document"]["file_id"]; ST["admin"] = chat; mark(); save_state()
        return tg("sendMessage", chat_id=chat, text="Готово: PDF сохранила, буду отправлять покупателям. Уведомления о продажах — сюда.")
    if text in (ADMIN_CODE, "/admin " + ADMIN_CODE):
        ST["admin"] = chat; mark(); save_state()
        return tg("sendMessage", chat_id=chat, text=f"Ты админ. PDF: {'есть' if ST.get('pdf') else 'нет — пришли файл с подписью-кодом'}. Статистика — /stats.")
    if text.startswith("/sbptest") and chat == admin_id():
        return sbp_pay(chat, uid, "check")
    if text.startswith("/stats") and chat == admin_id():
        return tg("sendMessage", chat_id=chat, text=stats_text(), parse_mode="HTML")

    if text.startswith("/start"):
        arg = text[6:].strip()
        free = arg.startswith("free")
        if free: arg = arg[5:]
        if u.get("src") == "direct" and arg and not arg.startswith("g") and arg not in ("buy", "book", "gift", "club", "sbp"):
            u["src"] = arg[:20]; mark()
        if free:
            tg("sendMessage", chat_id=chat, text="Здравствуй, милок! Я баба Зоя 👋 Обещала рецепты даром, держи.", reply_markup=menu_kb())
            return free_menu(chat)
        if re.fullmatch(r"r\d+(_\d+)*", arg):
            nums = [int(x) for x in arg[1:].split("_") if int(x) in LEAD]
            if nums: return send_lead(chat, uid, nums)
        if arg == "buy": return pay_choice(chat, "book", "Как удобнее заплатить, милок?")
        if arg.startswith("test"): return test_start(chat, u)
        if arg.startswith("sbp"): return sbp_pay(chat, uid, "promo" if u.get("promo", 0) > now() else "book")
        if arg == "gift": return pay_choice(chat, "gift", "Подарок — дело хорошее! Как заплатишь?")
        if arg == "club": return club_menu(chat, u)
        if arg.startswith("g") and len(arg) == 9 and arg != "gift": return redeem(chat, uid, arg[1:], m)
        if arg == "book": text = "/book"
        else:
            return greet(chat)
    if text.startswith("/book"):
        if has_paid(uid): return deliver(chat, "Вот твоя книжка, милок. Жми — и все рецепты откроются.")
        return tg("sendMessage", chat_id=chat, text="Покупку не нашла, милок. Если платил — напиши сюда, разберусь. А купить можно тут:", reply_markup=kb(*buy_rows()))
    if text.startswith("/buy"): return pay_choice(chat, "book", "Как удобнее заплатить, милок?")
    if text.startswith("/gift"): return pay_choice(chat, "gift", "Подарок — дело хорошее! Как заплатишь?")
    if text.startswith("/club"): return club_menu(chat, u)
    if text.startswith("/free"): return free_menu(chat)
    if text.startswith("/test"): return test_start(chat, u)
    if text.startswith("/help"):
        return tg("sendMessage", chat_id=chat, reply_markup=start_kb(), text=(
            "Как всё устроено:\n\n• Напиши, какой продукт есть, — подберу рецепт из книжки, один в подарок.\n• /free — семь рецептов даром, пришлю прямо сюда.\n• «Книжка» внизу чата — приложение с рецептами.\n"
            "• Вся книга — по СБП, картой или звёздами, один раз и навсегда. Купил, а закрыто — /book.\n"
            "• Подарить книжку — /gift, пришлю открытку со ссылкой.\n"
            + (f"• Клуб бабы Зои — /club, письмо с новым рецептом каждую неделю, {CLUB_PRICE} ⭐ в месяц.\n" if CLUB else "")
            + "• У кого книжка — может спрашивать меня прямо здесь, что приготовить.\n\n"
            "Рецепты — домашняя еда, а не лечение. Если есть болезни желудка, аллергия на мёд, беременность — посоветуйся с врачом."))
    if text.startswith("/"): return

    if text == M_FREE: return free_menu(chat)
    if text == M_ASK:
        return tg("sendMessage", chat_id=chat, text="Напиши, милок, какие продукты у тебя есть или что хочешь приготовить, подскажу 👇")
    if text == M_BOOK:
        if has_paid(uid): return deliver(chat, "Вот твоя книжка, милок. Жми, и все рецепты откроются.")
        return book_card(chat, "promo" if u.get("promo", 0) > now() else "book")

    # отзыв после просьбы
    if u.get("revs") == "wait" and (m.get("photo") or text):
        u["revs"] = "got"; mark()
        a = admin_id()
        if a: tg("copyMessage", chat_id=a, from_chat_id=chat, message_id=m["message_id"])
        return tg("sendMessage", chat_id=chat, text="Ох, спасибо, милок, порадовал бабушку! А можно я покажу твой отзыв в своём Instagram — без имени?",
                  reply_markup=kb([{"text": "Да, можно", "callback_data": "rev_yes"}, {"text": "Нет", "callback_data": "rev_no"}]))

    access = u.get("paid") or in_club(u)
    if text and SUPPORT.search(text) or (not text and (m.get("photo") or m.get("document"))):
        to_admin(f"Сообщение от {m['from'].get('first_name', '')} (@{m['from'].get('username', '-')}, id {chat}):\n\n{text[:3500]}")
        return tg("sendMessage", chat_id=chat, text="Поняла, милок, передала внучке — она разберётся и ответит.")
    if not text: return
    if not access:
        if not u.get("ai_trial") and not words(text):
            return tg("sendMessage", chat_id=chat, reply_markup=kb([B_FREE]),
                      text="Здравствуй, милок! Напиши, какой продукт у тебя есть — тыква, капуста, гречка, яблоки, — и я подберу рецепт из своей книжки. Один — в подарок.")
        if not u.get("ai_trial"):
            u["ai_trial"] = 1; mark()
            rs = find_recipes(text, 1)
            if rs:
                return tg("sendMessage", chat_id=chat, text=teaser(rs[0]), parse_mode="HTML", reply_markup=kb(*buy_rows(), [B_FREE]))
            if AI_KEY and ai_allowed(uid):
                tg("sendChatAction", chat_id=chat, action="typing")
                ans = ai_answer(uid, text)
                if ans:
                    return tg("sendMessage", chat_id=chat, text=ans + "\n\nА все сто рецептов — в книжке, и спрашивать меня тогда можно сколько хочешь.", reply_markup=kb(*buy_rows(), [B_FREE]))
            u["ai_trial"] = 0; mark()
            return tg("sendMessage", chat_id=chat, text="Напиши, милок, какой продукт у тебя есть — тыква, капуста, гречка, яблоки, — и я подберу рецепт.")
        return tg("sendMessage", chat_id=chat, reply_markup=kb(*buy_rows(), [B_FREE]),
                  text="Один рецепт я тебе уже подарила, милок. А все сто — в книжке, и спрашивать меня тогда можно сколько хочешь, про любой продукт.")
    if not AI_KEY:
        return tg("sendMessage", chat_id=chat, text="Спасибо, милок, прочитаю!")
    if not ai_allowed(uid):
        return tg("sendMessage", chat_id=chat, text="Ой, милок, наговорились мы сегодня. Завтра спрашивай — отвечу.")
    tg("sendChatAction", chat_id=chat, action="typing")
    ans = ai_answer(uid, text)
    return tg("sendMessage", chat_id=chat, text=ans or "Что-то я задумалась, милок. Спроси ещё раз чуть попозже.")

def redeem(chat, uid, code, m):
    g = ST["gifts"].get(code)
    if not g:
        return tg("sendMessage", chat_id=chat, text="Не нашла такого подарка, милок. Проверь ссылку.", reply_markup=start_kb())
    if g["to"] not in (None, uid):
        return tg("sendMessage", chat_id=chat, text="Этот подарок уже открыли, милок. Если это ошибка — напиши сюда.")
    first = g["to"] is None
    g["to"] = uid; u = user(uid, "gift"); u["paid"] = 1; u.setdefault("tp", now()); u["via"] = "gift"; mark()
    deliver(chat, "🎁 Тебе подарили мою книжку «Бабушкин стол», милок! Сто деревенских рецептов — теперь твои.\n\n"
                  "Нажми «Открыть всю книжку». А если захочешь — спрашивай меня прямо здесь, что приготовить.")
    if first:
        tg("sendMessage", chat_id=g["by"], text="Твой подарок открыли, милок! Спасибо, что делишься бабушкиными рецептами.")
    save_state()

def club_menu(chat, u):
    if not CLUB:
        return tg("sendMessage", chat_id=chat, text="Клуб скоро откроется, милок.")
    if in_club(u):
        n = released(); until = datetime.datetime.fromtimestamp(u["club"], MSK).strftime("%d.%m")
        rows = [[{"text": f"✉️ {CLUB[i]['title']}", "callback_data": f"cl_{i}"}] for i in range(n, -1, -1)]
        return tg("sendMessage", chat_id=chat, text=f"Ты в клубе, милок (оплачено до {until}). Вот все письма:", reply_markup=kb(*rows))
    link = club_link()
    return tg("sendMessage", chat_id=chat, reply_markup=kb([{"text": f"Вступить — {CLUB_PRICE} ⭐ в месяц", "url": link}]) if link else None,
              text=("✉️ <b>Клуб бабы Зои</b>\n\nРаз в неделю — письмо от меня: рецепт, которого нет в книжке, что заготавливать по сезону "
                    "и что у нас на пасеке. Плюс все прошлые письма сразу.\n\n"
                    f"{CLUB_PRICE} ⭐ в месяц. Отменить можно в любой момент в настройках Telegram."), parse_mode="HTML")

def on_callback(c):
    tg("answerCallbackQuery", callback_query_id=c["id"])
    d = c.get("data", ""); chat = c["message"]["chat"]["id"] if c.get("message") else c["from"]["id"]
    uid = c["from"]["id"]; u = user(uid)
    if d == "buy_choice": pay_choice(chat, "book", "Как удобнее заплатить, милок?")
    elif d in ("buy", "book_xtr"): invoice(chat, "book")
    elif d in ("buy_rub", "book_rub"): invoice(chat, "book", "RUB")
    elif d == "gift": pay_choice(chat, "gift", "Подарок — дело хорошее! Как заплатишь?")
    elif d == "gift_xtr": invoice(chat, "gift")
    elif d == "gift_rub": invoice(chat, "gift", "RUB")
    elif d in ("book_sbp", "gift_sbp"): sbp_pay(chat, uid, d[:-4])
    elif d == "promo_sbp":
        if u.get("promo", 0) > now(): sbp_pay(chat, uid, "promo")
        else: tg("sendMessage", chat_id=chat, text="Скидка уже закончилась, милок. Но книжка всё там же:", reply_markup=kb(*buy_rows()))
    elif d.startswith("ykc_"): yk_check(d[4:], chat)
    elif d == "test": test_start(chat, u)
    elif d.startswith("tq_"):
        _, i, j = d.split("_"); test_answer(chat, uid, u, int(i), int(j))
    elif d in ("promo", "promo_xtr", "promo_rub"):
        if u.get("promo", 0) > now():
            if d == "promo": pay_choice(chat, "promo", "Как удобнее заплатить, милок?")
            else: invoice(chat, "promo", "RUB" if d == "promo_rub" else "XTR")
        else: tg("sendMessage", chat_id=chat, text="Скидка уже закончилась, милок. Но книжка всё там же:", reply_markup=kb(*buy_rows()))
    elif d == "club": club_menu(chat, u)
    elif d == "free": free_menu(chat)
    elif d == "card": book_card(chat, "promo" if u.get("promo", 0) > now() else "book")
    elif d.startswith("fr_") and d[3:].isdigit() and int(d[3:]) in FREE: send_free(chat, uid, int(d[3:]))
    elif d.startswith("cl_") and in_club(u):
        i = int(d[3:])
        if 0 <= i <= released(): send_letter(chat, i)
    elif d in ("rev_yes", "rev_no"):
        u["revs"] = "done"; mark()
        tg("sendMessage", chat_id=chat, text="Спасибо, милок!" + (" Покажу без имени." if d == "rev_yes" else " Никому не покажу, только себе."))
        to_admin(f"Отзыв от id {uid}: " + ("можно показать в Instagram без имени ✅" if d == "rev_yes" else "показывать нельзя ❌"))

def on_precheckout(q):
    pl = q.get("invoice_payload"); uid = q["from"]["id"]
    cur = q.get("currency"); amt = q.get("total_amount", 0)
    ok = pl in ("book-v1", "promo-v1", "gift-v1", "club-v1") and (cur == "XTR" or (cur == "RUB" and YK and pl != "club-v1"))
    if ok and cur == "RUB": ok = amt == (RUB_PROMO if pl == "promo-v1" else RUB) * 100
    if pl == "check-v1" and cur == "RUB" and 0 < amt <= 10000: ok = True
    err = "Что-то не так со счётом, попробуй ещё раз из бота."
    if pl == "promo-v1" and user(uid).get("promo", 0) + 1800 < now():
        ok, err = False, "Скидка уже закончилась, милок. Книжку можно взять по обычной цене — /buy"
    tg("answerPreCheckoutQuery", pre_checkout_query_id=q["id"], ok=ok, **({} if ok else {"error_message": err}))


# ---------- фоновые задачи ----------
def periodic():
    if not daytime(): return
    t = now(); sent = 0
    for k, u in ST["users"].items():
        if sent >= 25: break
        if u.get("blocked"): continue
        chat = int(k)
        if not u.get("paid") and not in_club(u):
            if not u.get("d1") and t - u["t0"] > DAY:
                u["d1"] = t; mark(); sent += 1
                tg("sendMessage", chat_id=chat, text="Милок, ну как, попробовал что-нибудь из моих рецептов? 😊\nДержи ещё один, мой любимый 👇")
                send_card(chat, 26, kb([{"text": "📖 Вся книжка: 100 рецептов", "callback_data": "card"}]))
            elif u.get("d1") and not u.get("d2") and t - u["d1"] > 2 * DAY:
                u["d2"] = t; u["promo"] = t + DAY; mark(); sent += 1
                pk = kb([{"text": "Взять со скидкой", "callback_data": "promo"}])
                offer = "со скидкой"
                tg("sendMessage", chat_id=chat, reply_markup=pk,
                   text=(f"Вижу, заглядываешь, милок, а книжку всё не берёшь. Давай так: до завтра отдам книжку {offer}. "
                         "Сто рецептов, правила, меню на неделю — и спрашивать меня можно будет прямо тут."))
        elif not u.get("rev") and t - u.get("tp", t) > 7 * DAY:
            u["rev"] = t; u["revs"] = "wait"; mark(); sent += 1
            tg("sendMessage", chat_id=chat, text="Милок, неделя прошла, как книжка у тебя. Что уже приготовил? Пришли фото и пару слов — мне правда интересно.")
        if in_club(u) and CLUB:
            n = released()
            while u.get("cl", -1) < n:
                u["cl"] = u.get("cl", -1) + 1; mark(); send_letter(chat, u["cl"]); sent += 1

def stats_text():
    us = ST["users"].values(); src = collections.Counter(u.get("src", "direct") for u in us)
    paid = [u for u in ST["users"].values() if u.get("paid")]
    lines = ["<b>Статистика бабы Зои</b>", f"Всего людей: {len(ST['users'])}, купили: {len(paid)}"]
    lines += ["", "<b>Откуда пришли</b> (людей / купили):"]
    for s, n in src.most_common(12):
        b = sum(1 for u in paid if u.get("src", "direct") == s); lines.append(f"{s}: {n} / {b}")
    lines += ["", "<b>Продажи</b>:"] + [f"{k}: {v} шт., {ST.get('rub', {}).get(k, 0)} ₽ + {ST['stars'].get(k, 0)} ⭐" for k, v in ST["sales"].items() if not k.startswith("src:")]
    lines += ["", f"Взяли рецепты даром: {sum(1 for u in us if u.get('free'))} чел.", f"Пришли по кодовому слову: {sum(1 for u in us if u.get('lead'))} чел."]
    lines += ["", f"Дожим: 1-е письмо {sum(1 for u in us if u.get('d1'))}, скидка {sum(1 for u in ST['users'].values() if u.get('d2'))}",
              f"Подарков открыто: {sum(1 for g in ST['gifts'].values() if g['to'])} из {len(ST['gifts'])}",
              f"В клубе сейчас: {sum(1 for u in ST['users'].values() if in_club(u))}",
              f"Вопросов бабе Зое сегодня: {ST['ai_count'] if ST['ai_day'] == datetime.datetime.now(MSK).strftime('%Y-%m-%d') else 0}"]
    return "\n".join(lines)

def on_update(u):
    if "pre_checkout_query" in u: on_precheckout(u["pre_checkout_query"])
    elif "callback_query" in u: on_callback(u["callback_query"])
    elif "message" in u: on_message(u["message"])


STOP = False
def _stop(*a):
    global STOP
    STOP = True

def main():
    global BOOK
    signal.signal(signal.SIGTERM, _stop); signal.signal(signal.SIGINT, _stop)
    load_state(); BOOK = load_book(); build_index(); load_club()
    print(f"bot started: users={len(ST['users'])} recipes={len(IDX)} club={len(CLUB)}", flush=True)
    try: write_status()
    except Exception: traceback.print_exc()
    deadline = time.time() + RUN_SECONDS; offset = None; last_tick = 0
    while time.time() < deadline and not STOP:
        ups = tg("getUpdates", timeout=max(1, min(15 if ST.get("yk") else 25, int(deadline - time.time()))), offset=offset,
                 allowed_updates=["message", "callback_query", "pre_checkout_query"])
        for up in ups or []:
            offset = up["update_id"] + 1
            try: on_update(up)
            except Exception: traceback.print_exc()
        if time.time() - last_tick > 60:
            last_tick = time.time()
            try: periodic()
            except Exception: traceback.print_exc()
        try: yk_poll()
        except Exception: traceback.print_exc()
        if DIRTY and time.time() - LAST_SAVE > 300: save_state()
    if offset: tg("getUpdates", offset=offset, timeout=0)
    try: heartbeat()
    except Exception: traceback.print_exc()
    save_state(force=True)
    print("bot finished", flush=True)


if __name__ == "__main__":
    main()
