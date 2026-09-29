(() => {
const TG = (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData) ? window.Telegram.WebApp : null;
const C = window.CONFIG || {};
const $ = (s, el = document) => el.querySelector(s);
const esc = s => String(s == null ? "" : s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const norm = s => String(s).toLowerCase().replace(/ё/g, "е");

const ICON = {
  jar: '<path d="M9 5h14v3H9z"/><path d="M8 8h16c1 0 2 1 2 2v15c0 2-2 4-4 4H10c-2 0-4-2-4-4V10c0-1 1-2 2-2z"/><path d="M9 15c3-1.5 5 1.5 7 0s4-1.5 7 0"/>',
  loaf: '<path d="M4 20c0-7 5-12 12-12s12 5 12 12v2c0 2-1 3-3 3H7c-2 0-3-1-3-3z"/><path d="M11 12l-2 5M17 11l-2 6M23 12l-2 5"/>',
  honey: '<path d="M10 4l5 3v6l-5 3-5-3V7z"/><path d="M21 4l5 3v6l-5 3-5-3V7z"/><path d="M15.5 13l5 3v6l-5 3-5-3v-6z"/>',
  bowl: '<path d="M4 15h24c0 7-5 12-12 12S4 22 4 15z"/><path d="M11 11c-1-2 1-3 0-5M16 11c-1-2 1-3 0-5M21 11c-1-2 1-3 0-5"/>',
  pot: '<path d="M6 12h20v11c0 3-2 5-5 5H11c-3 0-5-2-5-5z"/><path d="M3 14h3M26 14h3M5 12c0-3 5-5 11-5s11 2 11 5"/><path d="M14 7c0-1.5 1-2 2-2s2 .5 2 2"/>',
  star: '<path d="M16 3l3.8 8 8.7 1-6.4 6 1.7 8.6L16 22.4 8.2 26.6 9.9 18 3.5 12l8.7-1z"/>',
  lock: '<rect x="7" y="14" width="18" height="13" rx="2"/><path d="M11 14v-4a5 5 0 0 1 10 0v4"/>',
  chev: '<path d="M12 7l8 9-8 9"/>',
  rules: '<path d="M8 4h16v24H8z"/><path d="M12 10h8M12 15h8M12 20h5"/>',
  cal: '<rect x="5" y="7" width="22" height="20" rx="2"/><path d="M5 13h22M11 4v6M21 4v6"/>',
  week: '<path d="M6 8h20M6 16h20M6 24h12"/>',
  scale: '<path d="M16 5v22M8 27h16M6 11h20M6 11l-3 8h6zM26 11l-3 8h6z"/>',
  note: '<path d="M7 5h14l5 5v17H7z"/><path d="M21 5v5h5M11 16h10M11 21h7"/>',
  clock: '<circle cx="16" cy="16" r="12"/><path d="M16 9v7l5 3"/>',
  back: '<path d="M20 7l-9 9 9 9"/>',
};
const ic = (n, cls = "") => `<svg class="${cls}" viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${ICON[n]}</svg>`;

/* ---------- storage: Telegram CloudStorage + localStorage ---------- */
const store = {
  async get(k) {
    let v = null;
    try { v = localStorage.getItem("bz_" + k); } catch (e) {}
    if (v == null && TG && TG.CloudStorage && TG.isVersionAtLeast && TG.isVersionAtLeast("6.9")) {
      v = await new Promise(res => { try { TG.CloudStorage.getItem(k, (err, val) => res(err ? null : val || null)); } catch (e) { res(null); } });
      if (v) try { localStorage.setItem("bz_" + k, v); } catch (e) {}
    }
    return v;
  },
  set(k, v) {
    try { localStorage.setItem("bz_" + k, v); } catch (e) {}
    try { if (TG && TG.CloudStorage && TG.isVersionAtLeast("6.9")) TG.CloudStorage.setItem(k, v); } catch (e) {}
  },
};

/* ---------- state ---------- */
const S = { pub: null, book: null, unlocked: false, fav: [], shop: {}, stack: [], tab: "home", filter: 0, q: "", timer: null,
  ny: null, nyBook: null, nyOpen: false, test: [] };
const BOT = () => "https://t.me/" + (C.bot || "BabaZoya_bot");
const nyRecipes = () => (S.nyOpen ? S.nyBook.recipes : (S.ny ? S.ny.free : []));
const nyRecipe = n => nyRecipes().find(r => r.n === n);
const nyIsOpen = n => S.nyOpen || (S.ny && S.ny.free.some(r => r.n === n));
const nyChap = i => S.ny.chapters.find(c => c.i === i);
const nyPhoto = i => "img/ny/ch" + i + ".jpg";
const recipes = () => (S.unlocked ? S.book.recipes : S.pub.free);
const getRecipe = n => recipes().find(r => r.n === n);
const isOpen = n => S.unlocked || S.pub.free.some(r => r.n === n);
const chap = i => S.pub.chapters.find(c => c.i === i);
const photo = i => (C.photos && C.photos[i]) || "img/cover.jpg";

function haptic(t = "light") { try { TG && TG.HapticFeedback.impactOccurred(t); } catch (e) {} }
function toast(msg, ms = 2600) { const t = $("#toast"); t.textContent = msg; t.classList.remove("hidden"); clearTimeout(t._h); t._h = setTimeout(() => t.classList.add("hidden"), ms); }

/* ---------- crypto ---------- */
function b64u(s) { s = s.replace(/-/g, "+").replace(/_/g, "/"); while (s.length % 4) s += "="; return Uint8Array.from(atob(s), c => c.charCodeAt(0)); }
async function decryptBook(keyStr, file = "book") {
  const buf = new Uint8Array(await (await fetch("data/" + file + ".enc?v=" + (C.v || 1))).arrayBuffer());
  const key = await crypto.subtle.importKey("raw", b64u(keyStr), "AES-GCM", false, ["decrypt"]);
  const plain = await crypto.subtle.decrypt({ name: "AES-GCM", iv: buf.slice(0, 12) }, key, buf.slice(12));
  return JSON.parse(new TextDecoder().decode(plain));
}

/* ---------- navigation ---------- */
function go(view, arg, push = true) {
  if (push) S.stack.push([view, arg]);
  render();
  window.scrollTo(0, 0);
}
function back() { S.stack.pop(); render(); }
function setTab(t) { S.tab = t; S.stack = []; render(); window.scrollTo(0, 0); }
function render() {
  const top = S.stack[S.stack.length - 1];
  const v = $("#view");
  document.querySelectorAll("#tabs button").forEach(b => b.classList.toggle("on", b.dataset.tab === S.tab));
  if (top) v.innerHTML = VIEWS[top[0]](top[1]); else v.innerHTML = VIEWS[S.tab]();
  if (TG && TG.BackButton) { S.stack.length ? TG.BackButton.show() : TG.BackButton.hide(); }
  else if (S.stack.length) { v.insertAdjacentHTML("afterbegin", `<button class="back" id="bk">${ic("back")}Назад</button>`); $("#bk").onclick = back; }
  bind(v);
}

/* ---------- views ---------- */
const VIEWS = {
home() {
  const name = TG && TG.initDataUnsafe && TG.initDataUnsafe.user ? TG.initDataUnsafe.user.first_name : "";
  const rs = recipes(); const d = rs[Math.floor(Date.now() / 864e5) % rs.length];
  const ch = S.pub.chapters.map(c => `<button class="chap" data-go="chapter" data-arg="${c.i}"><div class="ic" style="color:var(--red)">${ic(c.icon)}</div><b>${esc(c.title)}</b><span>${c.to - c.from + 1} рецептов${S.unlocked ? "" : " · " + S.pub.free.filter(r => r.ch === c.i).length + " открыто"}</span></button>`).join("");
  return `
  <section class="hero" style="background-image:url(img/cover.jpg)"><div class="dots"></div><div class="in">
    ${name ? `<div class="hi">Здравствуй, ${esc(name)}!</div>` : `<div class="kick">100 деревенских рецептов</div>`}
    <h1>Бабушкин стол</h1><p>Заготовки, выпечка и мёд для лёгкого живота</p></div></section>
  <div class="wrap">
    <button class="letter-card" data-go="letter"><img src="${photo(0)}" alt=""><div><b>Письмо от бабы Зои</b><div class="hand">Здравствуй, милок. Садись, расскажу, зачем эта книжка…</div></div></button>
    ${S.ny ? `<button class="nyban" data-go="ny" style="background-image:url(img/ny/cover.jpg)"><div class="in"><div class="kick">${S.nyOpen ? "Твоя вторая книжка" : "Новинка · 35 рецептов"}</div><b>Новогодний стол</b><span>Оливье, утка с яблоками, Наполеон — и план, как всё успеть к 31 декабря</span></div></button>` : ""}
    <div class="duo">
      <button class="mini gift" data-go="gift"><span class="e">🎁</span><b>Подарок</b><span>7 рецептов даром</span></button>
      <button class="mini test" data-go="test" data-arg="0"><span class="e">🥣</span><b>Тест</b><span>Какой у тебя живот</span></button>
    </div>
    ${S.unlocked ? "" : `<div class="unlock"><div class="kick" style="color:#FFD6BC">Вся книжка</div><h3>Откройте все 100 рецептов</h3><p>Сейчас открыто 7. После покупки — вся книга здесь и PDF в чат.</p><button class="btn" data-act="pay">Открыть всю книгу</button></div>`}
    <div class="section-t"><h2>Рецепт дня</h2></div>
    <button class="daily" data-go="recipe" data-arg="${d.n}"><div class="ph" style="background-image:url(${photo(d.ch)})"></div><div class="in"><div class="kick">№ ${d.n} · ${esc(chap(d.ch).title)}</div><h3>${esc(d.title)}</h3><p>${esc(d.intro)}</p></div></button>
    <div class="section-t"><h2>Главы</h2><button data-tab="list">Все рецепты</button></div>
    <div class="grid">${ch}</div>
    <div class="section-t"><h2>Ещё в книжке</h2></div>
    <div class="more">
      <button data-go="rules" style="color:var(--wine)">${ic("rules")}Бабушкины правила</button>
      <button data-go="week">${ic("week")}Неделя лёгкого живота</button>
      <button data-go="calendar">${ic("cal")}Календарь заготовок</button>
      <button data-go="measures">${ic("scale")}Таблица мер</button>
      <button data-go="notes">${ic("note")}Заметки пасечника</button>
      <button data-go="thanks">${ic("star")}Спасибо, милок</button>
    </div>
  </div>
  <div class="foot">${esc(S.pub.disclaimer)}</div>`;
},
list(arg) {
  const q = norm(S.q), f = S.filter;
  const all = S.pub.list.filter(r => !f || r.ch === f).filter(r => {
    if (!q) return true;
    if (norm(r.title).includes(q)) return true;
    const full = isOpen(r.n) && getRecipe(r.n);
    return full ? full.ing.some(x => norm(x).includes(q)) : false;
  });
  let html = `<div class="topbar"><h1>Рецепты</h1>
    <label class="search"><svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/></svg><input id="q" placeholder="Что есть дома? Например: тыква" value="${esc(S.q)}" enterkeyhint="search"></label>
    <div class="chips"><button class="chip ${f ? "" : "on"}" data-filter="0">Все</button>${S.pub.chapters.map(c => `<button class="chip ${f === c.i ? "on" : ""}" data-filter="${c.i}">${esc(c.title)}</button>`).join("")}</div></div>`;
  if (!all.length) return html + `<div class="empty"><span class="hand">Ничего не нашла, милок</span>${S.unlocked ? "Попробуй другое слово — «капуста», «мёд», «творог»." : "Поиск по продуктам работает во всей книжке после покупки."}</div>`;
  let last = 0;
  for (const r of all) {
    if (r.ch !== last) { html += `<div class="group-t">${esc(chap(r.ch).title)}</div>`; last = r.ch; }
    const open = isOpen(r.n);
    html += `<button class="item ${open ? "" : "locked"}" data-go="recipe" data-arg="${r.n}"><span class="no">${r.n}</span><span class="t"><b>${esc(r.title)}</b><small>${esc(r.time)}${open ? "" : " · в полной книжке"}</small></span><span class="r">${ic(open ? "chev" : "lock")}</span></button>`;
  }
  return html;
},
chapter(i) {
  i = +i; const c = chap(i);
  const items = S.pub.list.filter(r => r.ch === i).map(r => { const open = isOpen(r.n); return `<button class="item ${open ? "" : "locked"}" data-go="recipe" data-arg="${r.n}"><span class="no">${r.n}</span><span class="t"><b>${esc(r.title)}</b><small>${esc(r.time)}</small></span><span class="r">${ic(open ? "chev" : "lock")}</span></button>`; }).join("");
  const notes = S.unlocked ? S.book.notes.filter(n => n.ch === i) : [];
  return `<div class="rhead" style="background-image:url(${photo(i)})"><div class="dots"></div></div>
  <div class="rbody"><div class="kick">Глава ${i}</div><h1>${esc(c.title)}</h1><p class="muted" style="font-style:italic;margin:0 0 8px">${esc(c.intro)}</p></div>
  ${items}${notes.length ? `<div class="group-t">На заметку</div>` + notes.map(n => `<button class="item" data-go="note" data-arg="${S.book.notes.indexOf(n)}"><span class="no">✎</span><span class="t"><b>${esc(n.title)}</b><small>${esc(n.tag)}</small></span><span class="r">${ic("chev")}</span></button>`).join("") : ""}
  ${S.unlocked ? "" : `<div class="wrap"><div class="unlock"><h3>Вся глава — в полной книжке</h3><p>Сейчас открыто ${S.pub.free.filter(r => r.ch === i).length} из ${c.to - c.from + 1}.</p><button class="btn" data-act="pay">Открыть всю книгу</button></div></div>`}<div style="height:20px"></div>`;
},
recipe(n) {
  n = +n;
  if (!isOpen(n)) { setTimeout(() => { back(); paywall(n); }, 0); return ""; }
  const r = getRecipe(n), fav = S.fav.includes(n);
  const steps = r.steps.map((s, k) => { const t = parseTime(s); return `<li>${esc(s)}${t ? `<br><button class="tmr" data-timer="${t.sec}" data-label="${esc(r.title)} — шаг ${k + 1}">${ic("clock")}${t.label}</button>` : ""}</li>`; }).join("");
  return `<div class="rhead" style="background-image:url(${photo(r.ch)})"><div class="dots"></div></div>
  <div class="rbody">
    <div class="rtop"><div class="kick">№ ${r.n} · ${esc(chap(r.ch).title)}</div><button class="favbtn ${fav ? "on" : ""}" data-fav="${r.n}" aria-label="В избранное"><svg viewBox="0 0 24 24"><path d="M12 20s-7-4.5-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.5-7 10-7 10z"/></svg></button></div>
    <h1>${esc(r.title)}</h1><p class="intro">${esc(r.intro)}</p>
    <div class="meta"><span>⏱ ${esc(r.time)}</span><span>${esc(r.yield)}</span></div>
    <div class="box ing"><div class="lbl">Что нужно</div>${r.ing.map((x, k) => `<label><input type="checkbox" data-ing="${k}"><span>${esc(x)}</span></label>`).join("")}
      <button class="btn ghost addshop" data-shop="${r.n}">Добавить в список покупок</button></div>
    <div class="lbl">Как делаю</div><ol class="steps">${steps}</ol>
    <button class="btn cook" data-cook="${r.n}">Готовить по шагам</button>
    <div class="tip"><div class="k">Совет бабы Зои</div><div class="v">${esc(r.tip)}</div></div>
    ${r.warn ? `<div class="warn"><b>!</b><span>${esc(r.warn)}</span></div>` : ""}
    ${S.unlocked ? "" : `<div class="unlock" style="margin-bottom:24px"><h3>Понравилось?</h3><p>Ещё 93 рецепта, правила и меню на неделю — в полной книжке.</p><button class="btn" data-act="pay">Открыть всю книгу</button></div>`}
  </div>`;
},
fav() {
  const list = S.fav.map(getRecipe).filter(Boolean);
  if (!list.length) return `<div class="topbar"><h1>Избранное</h1></div><div class="empty"><span class="hand">Пока пусто</span>Нажми на сердечко в рецепте — и он будет здесь.</div>`;
  return `<div class="topbar"><h1>Избранное</h1></div>` + list.map(r => `<button class="item" data-go="recipe" data-arg="${r.n}"><span class="no">${r.n}</span><span class="t"><b>${esc(r.title)}</b><small>${esc(r.time)}</small></span><span class="r">${ic("chev")}</span></button>`).join("");
},
shop() {
  const keys = Object.keys(S.shop);
  if (!keys.length) return `<div class="topbar"><h1>Покупки</h1></div><div class="empty"><span class="hand">Список пустой</span>В рецепте нажми «Добавить в список покупок».</div>`;
  return `<div class="topbar"><h1>Покупки</h1></div>` + keys.map(n => { const r = getRecipe(+n); const g = S.shop[n]; return `<div class="shopgrp"><button class="x" data-unshop="${n}">Убрать</button><h3>${esc(r ? r.title : "Рецепт " + n)}</h3><div class="ing">${g.map((it, k) => `<label><input type="checkbox" data-sh="${n}:${k}" ${it.d ? "checked" : ""}><span>${esc(it.t)}</span></label>`).join("")}</div></div>`; }).join("") + `<div class="wrap"><button class="btn ghost" data-act="clearshop">Очистить список</button></div>`;
},
letter() {
  const L = S.pub.letter;
  return `<div class="page"><img class="top" src="${photo(0)}" alt=""><h1>Письмо от бабы Зои</h1>${L.slice(0, -1).map(p => `<p>${esc(p)}</p>`).join("")}<div class="sign">${esc(L[L.length - 1])}</div></div><div style="height:30px"></div>`;
},
thanks() {
  const T = S.pub.thanks;
  return `<div class="page"><h1>Спасибо, милок</h1>${T.map(p => `<p>${esc(p)}</p>`).join("")}<div class="sign">баба Зоя</div>
  ${C.channel ? `<a class="btn" href="${esc(C.channel)}" style="text-decoration:none;margin-top:10px">Канал бабы Зои</a>` : ""}</div><div style="height:30px"></div>`;
},
rules() {
  const list = S.unlocked ? S.book.rules : S.pub.rulesPreview;
  return `<div class="page"><h1>Бабушкины правила</h1><p class="muted" style="font-style:italic">Привычки, чтоб живот не болел. Это не медицина — так жили наши матери.</p>
  ${list.map((r, k) => `<div class="rule"><div class="n">${k + 1}</div><div><b>${esc(r.t)}</b><span>${esc(r.d)}</span></div></div>`).join("")}
  ${S.unlocked ? "" : `<div class="unlock"><h3>Ещё 12 правил</h3><p>Все 15 правил, меню на неделю и список покупок — в полной книжке.</p><button class="btn" data-act="pay">Открыть всю книгу</button></div>`}</div><div style="height:30px"></div>`;
},
week() {
  if (!S.unlocked) return lockedPage("Неделя лёгкого живота", "Меню на 7 дней из рецептов книжки и список покупок.");
  const B = S.book;
  return `<div class="page"><h1>Неделя лёгкого живота</h1><p>Не строгая диета — подсказка, как собрать неделю из простой еды.</p>
  ${B.week.map(d => `<div class="day"><b>${esc(d[0])}</b><div><i>Завтрак</i>${esc(d[1])}</div><div><i>Обед</i>${esc(d[2])}</div><div><i>Ужин</i>${esc(d[3])}</div></div>`).join("")}
  <p class="hand" style="font-size:22px;color:var(--wine);line-height:1.1">${esc(B.weekEvery)}</p>
  <h1 style="font-size:22px">Список покупок</h1>${B.shopping.map(g => `<div class="day"><b>${esc(g.t)}</b>${g.items.map(i => `<div>· ${esc(i)}</div>`).join("")}</div>`).join("")}</div><div style="height:30px"></div>`;
},
calendar() {
  if (!S.unlocked) return lockedPage("Календарь заготовок", "Что делать в каком месяце — по деревенскому календарю бабы Зои.");
  return `<div class="page"><h1>Календарь заготовок</h1><table class="tbl">${S.book.calendar.map(c => `<tr><td>${esc(c[0])}</td><td>${esc(c[1])}</td></tr>`).join("")}</table></div>`;
},
measures() {
  if (!S.unlocked) return lockedPage("Таблица мер", "Сколько граммов в стакане и ложке — чтобы готовить без весов.");
  return `<div class="page"><h1>Таблица мер</h1><p>Стакан — 200 мл, ложки — без горки.</p><table class="tbl"><tr><th>Продукт</th><th>Стакан</th><th>Ст. л.</th><th>Ч. л.</th></tr>${S.book.measures.map(m => `<tr>${m.map(x => `<td>${esc(x)}</td>`).join("")}</tr>`).join("")}</table></div>`;
},
notes() {
  if (!S.unlocked) return lockedPage("Заметки пасечника", "Как выбрать мёд, какой мёд какой, рассказ деда Коли и другие заметки.");
  return `<div class="topbar"><h1>Заметки</h1></div>` + S.book.notes.map((n, k) => `<button class="item" data-go="note" data-arg="${k}"><span class="no">✎</span><span class="t"><b>${esc(n.title)}</b><small>${esc(n.tag)} · ${esc(chap(n.ch).title)}</small></span><span class="r">${ic("chev")}</span></button>`).join("");
},
note(k) {
  const n = S.book.notes[+k];
  return `<div class="page"><div class="kick" style="margin-top:18px">${esc(n.tag)}</div><h1>${esc(n.title)}</h1>${n.body.map(p => `<p>${p}</p>`).join("")}</div><div style="height:30px"></div>`;
},
gift() {
  const items = S.pub.free.map(r => `<button class="item" data-go="recipe" data-arg="${r.n}"><span class="no">🎁</span><span class="t"><b>${esc(r.title)}</b><small>${esc(r.time)}</small></span><span class="r">${ic("chev")}</span></button>`).join("");
  return `<div class="page"><div class="kick" style="margin-top:18px">Подарок от бабы Зои</div><h1>7 рецептов даром</h1>
    <p class="hand" style="font-size:22px;line-height:1.1;color:var(--wine)">Держи, милок. С них я и сама начинала — капуста, огурцы, кисель да медовая вода.</p></div>
  ${items}
  <div class="wrap">
    <div class="giftbox"><div class="e">💝</div><h3>Подарить книжку</h3><p>Порадуй маму, бабушку или подругу: пришлю открытку со ссылкой, перешлёшь её тому, кому даришь. Откроется один раз.</p>
      <button class="btn" data-act="giftbuy">Подарить «Бабушкин стол»</button></div>
    ${S.unlocked ? "" : `<div class="unlock"><h3>А все 100 рецептов — в книжке</h3><p>Правила, меню на неделю и PDF в чат.</p><button class="btn" data-act="pay">Открыть всю книгу</button></div>`}
  </div><div style="height:24px"></div>`;
},
test(i) {
  i = +i || 0;
  if (i === 0) S.test = [];
  const T = TEST[i];
  return `<div class="page quiz"><div class="kick" style="margin-top:18px">Тест · вопрос ${i + 1} из ${TEST.length}</div>
    <div class="qprog">${TEST.map((_, k) => `<i class="${k <= i ? "on" : ""}"></i>`).join("")}</div>
    <h1>${esc(T[0])}</h1>
    ${T[1].map((o, j) => `<button class="opt" data-ans="${i}:${j}">${esc(o)}</button>`).join("")}
    ${i === 0 ? `<p class="muted" style="margin-top:16px;font-size:14px">Пять вопросов — отвечай как есть, я не ругаюсь 🙂</p>` : ""}</div>`;
},
result() {
  const score = S.test.reduce((a, b) => a + b, 0);
  const R = TEST_RES.find(x => score <= x[0]) || TEST_RES[TEST_RES.length - 1];
  const r = S.pub.free.find(x => x.n === R[3]) || S.pub.free[0];
  return `<div class="page quiz"><div class="kick" style="margin-top:18px">Твой результат</div><h1>${esc(R[1])}</h1><p>${esc(R[2])}</p>
    <button class="daily" data-go="recipe" data-arg="${r.n}"><div class="ph" style="background-image:url(${photo(r.ch)})"></div><div class="in"><div class="kick">Рецепт для тебя</div><h3>${esc(r.title)}</h3><p>${esc(r.intro)}</p></div></button>
    <p class="muted" style="font-size:13px;font-style:italic;margin-top:14px">Это не диагноз, а бабушкины наблюдения. Если живот болит всерьёз — к врачу.</p>
    ${S.unlocked ? "" : `<div class="unlock"><h3>Хочешь, чтобы живот был лёгкий?</h3><p>В книжке — 100 деревенских рецептов, 15 бабушкиных правил и меню на неделю.</p><button class="btn" data-act="pay">Открыть всю книгу</button></div>`}
    <button class="btn ghost" style="margin-top:12px" data-go="test" data-arg="0">Пройти ещё раз</button></div><div style="height:24px"></div>`;
},
ny() {
  const N = S.ny;
  const ch = N.chapters.map(c => `<button class="chap" data-go="nych" data-arg="${c.i}"><div class="ic" style="color:var(--red)">${ic(c.icon)}</div><b>${esc(c.title)}</b><span>${c.to - c.from + 1} рецептов</span></button>`).join("");
  return `<section class="hero" style="background-image:url(img/ny/cover.jpg)"><div class="dots"></div><div class="in">
    <div class="kick">35 праздничных рецептов</div><h1>Новогодний стол</h1><p>Салаты, закуски, горячее и торты — и план на 31 декабря</p></div></section>
  <div class="wrap">
    <button class="letter-card" data-go="nyletter"><img src="img/ny/face.jpg" alt=""><div><b>Письмо от бабы Зои</b><div class="hand">Новый год у нас в доме всегда был главным праздником…</div></div></button>
    ${S.nyOpen ? "" : `<div class="unlock"><div class="kick" style="color:#FFD6BC">Новогодняя книжка</div><h3>Все 35 рецептов и план по дням</h3><p>Сейчас открыто 2 рецепта. После покупки — всё здесь и PDF в чат.</p><button class="btn" data-act="nypay">Открыть «Новогодний стол»</button></div>`}
    <div class="section-t"><h2>Как всё успеть</h2></div>
    <div class="more">
      <button data-go="nyplan" style="color:var(--wine)">${ic("cal")}План по дням</button>
      <button data-go="nymenu">${ic("note")}Меню и покупки</button>
      <button data-go="nylight">${ic("rules")}Стол без тяжести</button>
      <button data-go="nyleft">${ic("jar")}Как хранить остатки</button>
    </div>
    <div class="section-t"><h2>Главы</h2></div>
    <div class="grid">${ch}</div>
  </div>
  <div class="foot">${esc(N.disclaimer)}</div>`;
},
nyletter() {
  const L = S.ny.letter;
  return `<div class="page"><img class="top" src="img/ny/face.jpg" alt=""><h1>Письмо от бабы Зои</h1>${L.slice(0, -1).map(p => `<p>${esc(p)}</p>`).join("")}<div class="sign">${esc(L[L.length - 1])}</div></div><div style="height:30px"></div>`;
},
nych(i) {
  i = +i; const c = nyChap(i);
  const items = S.ny.list.filter(r => r.ch === i).map(r => { const open = nyIsOpen(r.n); return `<button class="item ${open ? "" : "locked"}" data-go="nyrec" data-arg="${r.n}"><span class="no">${r.n}</span><span class="t"><b>${esc(r.title)}</b><small>${esc(r.time)}</small></span><span class="r">${ic(open ? "chev" : "lock")}</span></button>`; }).join("");
  return `<div class="rhead" style="background-image:url(${nyPhoto(i)})"><div class="dots"></div></div>
  <div class="rbody"><div class="kick">Глава ${i}</div><h1>${esc(c.title)}</h1><p class="muted" style="font-style:italic;margin:0 0 8px">${esc(c.intro)}</p></div>
  ${items}${S.nyOpen ? "" : `<div class="wrap"><div class="unlock"><h3>Вся глава — в новогодней книжке</h3><p>35 рецептов, план по дням и список покупок.</p><button class="btn" data-act="nypay">Открыть «Новогодний стол»</button></div></div>`}<div style="height:20px"></div>`;
},
nyrec(n) {
  n = +n;
  if (!nyIsOpen(n)) { setTimeout(() => { back(); nyPay(); }, 0); return ""; }
  const r = nyRecipe(n);
  const steps = r.steps.map((s, k) => { const t = parseTime(s); return `<li>${esc(s)}${t ? `<br><button class="tmr" data-timer="${t.sec}" data-label="${esc(r.title)} — шаг ${k + 1}">${ic("clock")}${t.label}</button>` : ""}</li>`; }).join("");
  return `<div class="rhead" style="background-image:url(${nyPhoto(r.ch)})"><div class="dots"></div></div>
  <div class="rbody">
    <div class="rtop"><div class="kick">№ ${r.n} · ${esc(nyChap(r.ch).title)}</div></div>
    <h1>${esc(r.title)}</h1><p class="intro">${esc(r.intro)}</p>
    <div class="meta"><span>⏱ ${esc(r.time)}</span><span>${esc(r.yield)}</span></div>
    <div class="box ing"><div class="lbl">Что нужно</div>${r.ing.map((x, k) => `<label><input type="checkbox" data-ing="${k}"><span>${esc(x)}</span></label>`).join("")}</div>
    <div class="lbl">Как делаю</div><ol class="steps">${steps}</ol>
    <button class="btn cook" data-nycook="${r.n}">Готовить по шагам</button>
    <div class="tip"><div class="k">Совет бабы Зои</div><div class="v">${esc(r.tip)}</div></div>
    ${r.warn ? `<div class="warn"><b>!</b><span>${esc(r.warn)}</span></div>` : ""}
    ${S.nyOpen ? "" : `<div class="unlock" style="margin-bottom:24px"><h3>Понравилось?</h3><p>Ещё 33 праздничных рецепта и план, как всё успеть к 31-му.</p><button class="btn" data-act="nypay">Открыть «Новогодний стол»</button></div>`}
  </div>`;
},
nyplan() {
  const list = S.nyOpen ? S.nyBook.plan : S.ny.planPreview;
  return `<div class="page"><h1>Как всё успеть</h1><p class="muted" style="font-style:italic">Так я готовлю уже сорок лет. Номера — это рецепты из книжки.</p>
  ${list.map(d => `<div class="day"><b>${esc(d.d)}</b>${d.items.map(i => `<div>· ${esc(i)}</div>`).join("")}</div>`).join("")}
  ${S.nyOpen ? "" : `<div class="unlock"><h3>Дальше — в книжке</h3><p>План на 29, 30 и 31 декабря по часам, меню и список покупок.</p><button class="btn" data-act="nypay">Открыть «Новогодний стол»</button></div>`}</div><div style="height:30px"></div>`;
},
nymenu() {
  if (!S.nyOpen) return nyLocked("Меню и список покупок", "Меню на 8 человек и готовый список, что купить к празднику.");
  const B = S.nyBook;
  return `<div class="page"><h1>${esc(B.menu.t)}</h1><div class="day">${B.menu.items.map(i => `<div>· ${esc(i)}</div>`).join("")}</div>
  <h1 style="font-size:22px">Список покупок</h1>${B.shopping.map(g => `<div class="day"><b>${esc(g.t)}</b>${g.items.map(i => `<div>· ${esc(i)}</div>`).join("")}</div>`).join("")}</div><div style="height:30px"></div>`;
},
nylight() {
  if (!S.nyOpen) return nyLocked("Стол без тяжести", "Как отпраздновать и первого января не лежать пластом.");
  return `<div class="page"><h1>Стол без тяжести</h1><p class="muted" style="font-style:italic">Не диета — просто как мы жили.</p>
  ${S.nyBook.light.map((r, k) => `<div class="rule"><div class="n">${k + 1}</div><div><b>${esc(r.t)}</b><span>${esc(r.d)}</span></div></div>`).join("")}</div><div style="height:30px"></div>`;
},
nyleft() {
  if (!S.nyOpen) return nyLocked("Как хранить остатки", "Сколько стоят оливье, шуба, холодец и утка — и что из них приготовить.");
  return `<div class="page"><h1>Как хранить остатки</h1><table class="tbl">${S.nyBook.left.map(c => `<tr><td>${esc(c.t)}</td><td>${esc(c.d)}</td></tr>`).join("")}</table></div>`;
},
};
function nyLocked(t, d) {
  return `<div class="page"><h1>${esc(t)}</h1><p>${esc(d)}</p><div class="unlock"><h3>Это в новогодней книжке</h3><p>35 рецептов, план по дням, меню и список покупок.</p><button class="btn" data-act="nypay">Открыть «Новогодний стол»</button></div></div>`;
}
const TEST = [
  ["Как живот после обеда?", ["Легко, будто и не ел", "Бывает тяжесть", "Почти всегда камнем, клонит в сон"]],
  ["Квашеное ешь — капусту, огурцы, квас?", ["Каждый день", "Иногда", "Почти никогда"]],
  ["Что у тебя на завтрак?", ["Каша или что-то домашнее", "Бутерброд да кофе", "Ничего, на бегу"]],
  ["Какой хлеб ешь?", ["Свой или ржаной", "Обычный магазинный", "Батоны да выпечку"]],
  ["Как после праздников?", ["Всё хорошо", "Пару дней тяжело", "Неделю в себя прихожу"]],
];
const TEST_RES = [
  [3, "Живот у тебя, милок, лёгкий 🌿", "Ешь ты по-деревенски, живот и благодарит. Держи медовую воду по утрам — так и держать.", 41],
  [6, "Живот просит подмоги 🥬", "Ест живот много магазинного, а живого мало. Начни с простого — квашеной капусты к обеду.", 1],
  [10, "Живот устал, милок 🍯", "Тяжёлое да на бегу — вот живот и устаёт. Начни утро с овсяного киселя, как у нас в деревне.", 56],
];
function lockedPage(t, d) {
  return `<div class="page"><h1>${esc(t)}</h1><p>${esc(d)}</p><div class="unlock"><h3>Это в полной книжке</h3><p>Все 100 рецептов, правила, меню и таблицы.</p><button class="btn" data-act="pay">Открыть всю книгу</button></div></div>`;
}

/* ---------- timers ---------- */
function parseTime(s) {
  let m = s.match(/(\d+)(?:\s*[–-]\s*(\d+))?\s*(минут|мин\b)/i);
  if (m) { const v = +(m[2] || m[1]); if (v <= 180) return { sec: v * 60, label: `${v} мин` }; }
  m = s.match(/(\d+(?:,\d)?)(?:\s*[–-]\s*(\d+))?\s*час/i);
  if (m && !/ноч|дн/.test(s.slice(0, 0))) { const v = parseFloat((m[2] || m[1]).replace(",", ".")); if (v <= 3) return { sec: Math.round(v * 3600), label: `${String(v).replace(".", ",")} ч` }; }
  return null;
}
function fmt(sec) { const h = Math.floor(sec / 3600), m = Math.floor(sec % 3600 / 60), s = sec % 60; return (h ? h + ":" + String(m).padStart(2, "0") : m) + ":" + String(s).padStart(2, "0"); }
function startTimer(sec, label) {
  stopTimer();
  const end = Date.now() + sec * 1000;
  const bar = document.createElement("div"); bar.className = "timerbar"; bar.innerHTML = `<b></b><span>${esc(label)}</span><button>Стоп</button>`;
  document.body.appendChild(bar);
  bar.querySelector("button").onclick = stopTimer;
  const tick = () => {
    const left = Math.max(0, Math.round((end - Date.now()) / 1000));
    bar.querySelector("b").textContent = fmt(left);
    if (!left) { stopTimer(); try { TG.HapticFeedback.notificationOccurred("success"); } catch (e) {} (TG && TG.showAlert) ? TG.showAlert("Готово, милок! " + label) : alert("Готово! " + label); }
  };
  tick(); S.timer = { bar, h: setInterval(tick, 1000) };
  haptic("medium");
}
function stopTimer() { if (S.timer) { clearInterval(S.timer.h); S.timer.bar.remove(); S.timer = null; } }

/* ---------- cook mode ---------- */
function cook(n, rec) {
  const r = rec || getRecipe(n); let k = 0;
  const el = document.createElement("div"); el.className = "cookmode"; document.body.appendChild(el);
  const draw = () => {
    const t = parseTime(r.steps[k]);
    el.innerHTML = `<div class="top"><span class="kick">${esc(r.title)}</span><button class="x">Закрыть</button></div>
    <div class="prog">${r.steps.map((_, i) => `<i class="${i <= k ? "on" : ""}"></i>`).join("")}</div>
    <div class="body"><div class="n">Шаг ${k + 1} из ${r.steps.length}</div><div class="s">${esc(r.steps[k])}</div>${t ? `<div><button class="tmr" style="font-size:15px;padding:9px 14px;margin-top:16px">${ic("clock")}Таймер ${t.label}</button></div>` : ""}</div>
    <div class="nav">${k ? `<button class="btn ghost" data-k="-1">Назад</button>` : ""}<button class="btn" data-k="1">${k === r.steps.length - 1 ? "Готово!" : "Дальше"}</button></div>`;
    el.querySelector(".x").onclick = () => el.remove();
    const tb = el.querySelector(".tmr"); if (tb) tb.onclick = () => startTimer(t.sec, `${r.title} — шаг ${k + 1}`);
    el.querySelectorAll("[data-k]").forEach(b => b.onclick = () => { haptic(); const d = +b.dataset.k; if (k + d >= r.steps.length) { el.remove(); toast("На здоровье, милок!"); return; } k += d; draw(); });
  };
  draw();
}

/* ---------- paywall ---------- */
function paywall() {
  const sh = $("#sheet");
  sh.innerHTML = `<div class="pane pay"><div class="ph" style="background-image:url(img/cover.jpg)"><div class="dots"></div></div><div class="in">
  <div class="kick">Полная книжка</div><h2>Бабушкин стол</h2>
  <ul><li>100 деревенских рецептов с пошаговыми таймерами</li><li>Поиск «что есть дома» по продуктам</li><li>15 бабушкиных правил и меню на неделю со списком покупок</li><li>Заметки пасечника и рассказы деда Коли</li><li>PDF-книжка на 132 страницы — в чат</li></ul>
  ${C.sbp ? `<button class="btn" data-act="buysbp">⚡ СБП — через приложение банка</button><div style="height:8px"></div>` : ""}
  ${C.invoiceRub ? `<button class="btn${C.sbp ? " ghost" : ""}" data-act="buyrub">💳 Картой</button><button class="btn ghost" style="margin-top:8px" data-act="buy">⭐ Звёздами Telegram</button>` : `<button class="btn" data-act="buy">Купить книжку</button>`}
  <button class="btn ghost" style="margin-top:8px" data-act="close">Позже</button>
  <small>${C.invoiceRub ? (C.sbp ? "Оплата по СБП, картой или звёздами Telegram." : "Оплата картой или звёздами Telegram.") : "Оплата звёздами Telegram."} Книжка откроется здесь навсегда.</small></div></div>`;
  sh.classList.remove("hidden");
  sh.onclick = e => { if (e.target === sh) sh.classList.add("hidden"); };
  bind(sh);
}
function nyPay() {
  const sh = $("#sheet");
  sh.innerHTML = `<div class="pane pay"><div class="ph" style="background-image:url(img/ny/cover.jpg)"><div class="dots"></div></div><div class="in">
  <div class="kick">Новогодняя книжка</div><h2>Новогодний стол</h2>
  <ul><li>35 праздничных рецептов: оливье, шуба, холодец, утка, пельмени, Наполеон</li><li>План по дням с 28 по 31 декабря — как всё успеть</li><li>Меню на 8 человек и список покупок</li><li>Стол без тяжести и как хранить остатки</li><li>PDF-книжка — в чат</li></ul>
  ${C.sbp ? `<button class="btn" data-act="nysbp">⚡ СБП — через приложение банка</button><div style="height:8px"></div>` : ""}
  <button class="btn${C.sbp ? " ghost" : ""}" data-act="nybot">💳 Картой или ⭐ звёздами</button>
  <button class="btn ghost" style="margin-top:8px" data-act="close">Позже</button>
  <small>Оплата в боте бабы Зои. Книжка откроется здесь навсегда.</small></div></div>`;
  sh.classList.remove("hidden");
  sh.onclick = e => { if (e.target === sh) sh.classList.add("hidden"); };
  bind(sh);
}
function toBot(start) {
  haptic();
  const link = BOT() + "?start=" + start;
  if (TG) { try { TG.openTelegramLink(link); setTimeout(() => { try { TG.close(); } catch (e) {} }, 400); return; } catch (e) {} }
  location.href = link;
}
function buy(link) {
  link = link || C.invoice;
  if (!TG || !link) { toast("Открой книжку из бота @" + (C.bot || "")); return; }
  haptic();
  try { TG.openInvoice(link, onPaid); }
  catch (e) {
    try { TG.openTelegramLink(link); } catch (e2) { toast("Не открылась оплата: " + (e2.message || e.message || e)); }
  }
}
function buySbp() {
  haptic();
  const link = "https://t.me/" + (C.bot || "BabaZoya_bot") + "?start=sbp";
  try { TG.openTelegramLink(link); setTimeout(() => { try { TG.close(); } catch (e) {} }, 400); }
  catch (e) { location.href = link; }
}
function onPaid(status) {
    if (status === "paid") {
      $("#sheet").classList.add("hidden");
      TG.showAlert("Спасибо, милок! Баба Зоя прислала в чат книжку и кнопку «Открыть книжку». Нажми её — и все рецепты откроются.", () => TG.close());
    } else if (status === "failed") toast("Оплата не прошла, попробуй ещё раз");
}

/* ---------- events ---------- */
function bind(root) {
  root.querySelectorAll("[data-go]").forEach(b => b.onclick = () => { haptic(); go(b.dataset.go, b.dataset.arg); });
  root.querySelectorAll("[data-tab]").forEach(b => b.onclick = () => { haptic(); setTab(b.dataset.tab); });
  root.querySelectorAll("[data-filter]").forEach(b => b.onclick = () => { S.filter = +b.dataset.filter; render(); });
  root.querySelectorAll("[data-fav]").forEach(b => b.onclick = () => {
    const n = +b.dataset.fav; const i = S.fav.indexOf(n);
    i >= 0 ? S.fav.splice(i, 1) : S.fav.unshift(n); store.set("fav", JSON.stringify(S.fav));
    b.classList.toggle("on", i < 0); haptic("medium"); toast(i < 0 ? "Добавила в избранное" : "Убрала из избранного");
  });
  root.querySelectorAll("[data-shop]").forEach(b => b.onclick = () => {
    const r = getRecipe(+b.dataset.shop); S.shop[r.n] = r.ing.map(t => ({ t, d: false }));
    store.set("shop", JSON.stringify(S.shop)); haptic("medium"); toast("Записала в покупки");
  });
  root.querySelectorAll("[data-unshop]").forEach(b => b.onclick = () => { delete S.shop[b.dataset.unshop]; store.set("shop", JSON.stringify(S.shop)); render(); });
  root.querySelectorAll("[data-sh]").forEach(b => b.onchange = () => { const [n, k] = b.dataset.sh.split(":"); S.shop[n][+k].d = b.checked; store.set("shop", JSON.stringify(S.shop)); });
  root.querySelectorAll("[data-timer]").forEach(b => b.onclick = () => startTimer(+b.dataset.timer, b.dataset.label));
  root.querySelectorAll("[data-cook]").forEach(b => b.onclick = () => cook(+b.dataset.cook));
  root.querySelectorAll("[data-nycook]").forEach(b => b.onclick = () => cook(0, nyRecipe(+b.dataset.nycook)));
  root.querySelectorAll("[data-ans]").forEach(b => b.onclick = () => {
    const [i, j] = b.dataset.ans.split(":").map(Number); haptic();
    S.test = S.test.slice(0, i); S.test[i] = j;
    S.stack.pop();
    if (i + 1 < TEST.length) go("test", String(i + 1)); else go("result");
  });
  root.querySelectorAll("[data-act]").forEach(b => b.onclick = () => {
    const a = b.dataset.act;
    if (a === "nypay") nyPay(); else if (a === "nysbp") toBot("nysbp"); else if (a === "nybot") toBot("ny"); else if (a === "giftbuy") toBot("gift");
    else if (a === "pay") paywall(); else if (a === "buy") buy(); else if (a === "buyrub") buy(C.invoiceRub); else if (a === "buysbp") buySbp(); else if (a === "close") $("#sheet").classList.add("hidden");
    else if (a === "clearshop") { S.shop = {}; store.set("shop", "{}"); render(); }
  });
  const q = root.querySelector("#q");
  if (q) { q.oninput = () => { S.q = q.value; const pos = q.selectionStart; render(); const n = $("#q"); n.focus(); n.setSelectionRange(pos, pos); }; }
}

/* ---------- boot ---------- */
async function boot() {
  if (TG) {
    TG.ready(); TG.expand();
    if (TG.colorScheme === "dark") document.documentElement.classList.add("dark");
    try { TG.setHeaderColor(TG.colorScheme === "dark" ? "#1E1714" : "#FBF5EA"); TG.setBackgroundColor(TG.colorScheme === "dark" ? "#1E1714" : "#FBF5EA"); } catch (e) {}
    TG.BackButton && TG.BackButton.onClick(back);
    TG.onEvent && TG.onEvent("themeChanged", () => document.documentElement.classList.toggle("dark", TG.colorScheme === "dark"));
  } else if (/dark/.test(location.search) || (window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches)) document.documentElement.classList.add("dark");
  S.pub = await (await fetch("data/public.json?v=" + (C.v || 1))).json();
  try { S.ny = await (await fetch("data/ny_public.json?v=" + (C.v || 1))).json(); } catch (e) { S.ny = null; }
  try { S.fav = JSON.parse(await store.get("fav") || "[]"); } catch (e) {}
  try { S.shop = JSON.parse(await store.get("shop") || "{}"); } catch (e) {}
  let key = null;
  const m = (location.search + "&" + location.hash).match(/[?&#]k=([\w-]{20,})/);
  const sp = TG && TG.initDataUnsafe && TG.initDataUnsafe.start_param;
  if (m) key = m[1]; else if (sp && sp.startsWith("k")) key = sp.slice(1);
  if (!key) key = await store.get("key");
  let nk = null;
  const nm = (location.search + "&" + location.hash).match(/[?&#]n=([\w-]{20,})/);
  if (nm) nk = nm[1]; else if (sp && sp.startsWith("n")) nk = sp.slice(1);
  if (!nk) nk = await store.get("keyny");
  if (nk && S.ny) {
    try { S.nyBook = await decryptBook(nk, "ny"); S.nyOpen = true; store.set("keyny", nk);
      if (nm || (sp && sp.startsWith("n"))) { try { history.replaceState(null, "", location.pathname); } catch (e) {} S.stack = [["ny"]]; setTimeout(() => toast("Новогодняя книжка открыта. С наступающим!"), 400); } }
    catch (e) { console.warn("bad ny key", e); }
  }
  if (key) {
    try { S.book = await decryptBook(key); S.unlocked = true; store.set("key", key); if (m || sp) { try { history.replaceState(null, "", location.pathname); } catch (e) {} } if (m || sp) setTimeout(() => toast("Книжка открыта. Приятного аппетита!"), 400); }
    catch (e) { console.warn("bad key", e); }
  }
  render();
}
document.querySelectorAll("#tabs button").forEach(b => b.onclick = () => { haptic(); setTab(b.dataset.tab); });
boot();
})();
