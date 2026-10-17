(function () {
  'use strict';

  var OPS_KEY = 'wallet.operations';
  var TASKS_KEY = 'wallet.calendar.tasks';
  var MAX_TITLE = 60;
  var MONTHS = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'];

  function $(id) { return document.getElementById(id); }
  function pad(n) { return String(n).padStart(2, '0'); }
  function toKey(y, m, d) { return y + '-' + pad(m + 1) + '-' + pad(d); }
  function todayKey() {
    var n = new Date();
    return toKey(n.getFullYear(), n.getMonth(), n.getDate());
  }
  function keyToRu(key) {
    var p = key.split('-');
    return p[2] + '.' + p[1] + '.' + p[0];
  }
  function newId() {
    return Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
  }
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function loadArray(key) {
    try {
      var v = JSON.parse(localStorage.getItem(key));
      return Array.isArray(v) ? v : [];
    } catch (e) {
      return [];
    }
  }
  function saveArray(key, arr) {
    try { localStorage.setItem(key, JSON.stringify(arr)); } catch (e) { /* хранилище недоступно */ }
  }
  function groupNum(n) {
    return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, '\u00A0');
  }

  /* ---------------- Кошелёк ---------------- */
  var ops = loadArray(OPS_KEY).filter(function (o) {
    return o && typeof o === 'object' && typeof o.amount === 'number' && (o.type === 'income' || o.type === 'expense');
  });

  function renderWallet() {
    var balance = 0;
    ops.forEach(function (o) { balance += o.type === 'income' ? o.amount : -o.amount; });
    var b = $('balance');
    b.textContent = (balance < 0 ? '\u2212' : '') + groupNum(Math.abs(balance)) + '\u00A0₽';
    b.className = 'bal-value' + (balance < 0 ? ' neg' : '');

    var list = $('op-list');
    list.textContent = '';
    if (!ops.length) {
      var empty = el('div', 'empty');
      empty.appendChild(el('b', null, 'Операций пока нет'));
      empty.appendChild(el('span', null, 'Добавьте первую операцию — доход или расход, и она появится здесь.'));
      list.appendChild(empty);
      return;
    }
    for (var i = ops.length - 1; i >= 0; i--) {
      var o = ops[i];
      var row = el('div', 'op');
      row.appendChild(el('div', 'dt', typeof o.date === 'string' && o.date.length === 10 ? keyToRu(o.date) : ''));
      row.appendChild(el('div', 'nm', String(o.title || '')));
      var inc = o.type === 'income';
      row.appendChild(el('div', 'sum ' + (inc ? 'pos' : 'neg'), (inc ? '+' : '\u2212') + groupNum(o.amount) + '\u00A0₽'));
      list.appendChild(row);
    }
  }

  $('op-form').addEventListener('submit', function (e) {
    e.preventDefault();
    var amountInput = $('op-amount');
    var titleInput = $('op-title');
    var err = $('op-error');
    var raw = amountInput.value.trim();
    var title = titleInput.value.trim();
    var type = document.querySelector('input[name="op-type"]:checked').value;
    amountInput.classList.remove('invalid');
    titleInput.classList.remove('invalid');
    err.textContent = '';

    if (!/^\d{1,12}$/.test(raw) || Number(raw) < 1) {
      err.textContent = 'Сумма — целое число от 1';
      amountInput.classList.add('invalid');
      return;
    }
    if (!title) {
      err.textContent = 'Укажите, на что деньги';
      titleInput.classList.add('invalid');
      return;
    }
    if (title.length > MAX_TITLE) {
      err.textContent = 'Подпись не длиннее 60 символов';
      titleInput.classList.add('invalid');
      return;
    }
    ops.push({ id: newId(), date: todayKey(), type: type, amount: Number(raw), title: title });
    saveArray(OPS_KEY, ops);
    amountInput.value = '';
    titleInput.value = '';
    renderWallet();
  });

  /* ---------------- Календарь ---------------- */
  var tasks = loadArray(TASKS_KEY).filter(function (t) {
    return t && typeof t === 'object' && typeof t.id === 'string' &&
      typeof t.date === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(t.date) && typeof t.title === 'string';
  }).map(function (t) {
    return { id: t.id, date: t.date, title: t.title, done: t.done === true };
  });

  var now = new Date();
  var view = { y: now.getFullYear(), m: now.getMonth() };
  var selected = todayKey();

  function saveTasks() { saveArray(TASKS_KEY, tasks); }

  function datesWithTasks() {
    var set = {};
    tasks.forEach(function (t) { set[t.date] = true; });
    return set;
  }

  function renderGrid() {
    $('cal-title').textContent = MONTHS[view.m] + ' ' + view.y;
    var grid = $('cal-grid');
    grid.textContent = '';
    var shift = (new Date(view.y, view.m, 1).getDay() + 6) % 7;
    var days = new Date(view.y, view.m + 1, 0).getDate();
    var has = datesWithTasks();
    var today = todayKey();
    var i;
    for (i = 0; i < shift; i++) {
      var blank = el('div', 'cell blank');
      blank.setAttribute('aria-hidden', 'true');
      grid.appendChild(blank);
    }
    for (var d = 1; d <= days; d++) {
      var key = toKey(view.y, view.m, d);
      var cls = 'cell';
      if (key === today) cls += ' today';
      if (key === selected) cls += ' selected';
      var btn = el('button', cls);
      btn.type = 'button';
      btn.dataset.date = key;
      btn.setAttribute('aria-pressed', key === selected ? 'true' : 'false');
      var label = String(d) + ' ' + MONTHS[view.m].toLowerCase();
      if (has[key]) label += ', есть дела';
      if (key === today) label += ', сегодня';
      btn.setAttribute('aria-label', label);
      btn.appendChild(el('span', 'num', String(d)));
      if (has[key]) btn.appendChild(el('span', 'dot'));
      grid.appendChild(btn);
    }
  }

  function plural(n) {
    var a = n % 100, b = n % 10;
    if (a >= 11 && a <= 14) return n + ' дел';
    if (b === 1) return n + ' дело';
    if (b >= 2 && b <= 4) return n + ' дела';
    return n + ' дел';
  }

  function renderDay() {
    $('day-title').textContent = 'Дела на ' + keyToRu(selected);
    var list = $('day-list');
    list.textContent = '';
    var dayTasks = tasks.filter(function (t) { return t.date === selected; });
    $('day-count').textContent = plural(dayTasks.length);
    $('day-empty').hidden = dayTasks.length > 0;
    dayTasks.forEach(function (t) {
      var li = el('li', 'task' + (t.done ? ' done' : ''));
      li.dataset.id = t.id;
      var label = el('label');
      var cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.checked = t.done;
      cb.className = 'task-done';
      cb.setAttribute('aria-label', 'Выполнено: ' + t.title);
      label.appendChild(cb);
      label.appendChild(el('span', 'name', t.title));
      li.appendChild(label);
      var del = el('button', 'del', 'Удалить');
      del.type = 'button';
      del.dataset.id = t.id;
      li.appendChild(del);
      list.appendChild(li);
    });
  }

  function clearTaskError() {
    $('task-error').textContent = '';
    $('task-title').classList.remove('invalid');
  }

  function renderCalendar() {
    renderGrid();
    renderDay();
  }

  function shiftMonth(delta) {
    var d = new Date(view.y, view.m + delta, 1);
    view.y = d.getFullYear();
    view.m = d.getMonth();
    renderGrid();
  }

  $('cal-prev').addEventListener('click', function () { shiftMonth(-1); });
  $('cal-next').addEventListener('click', function () { shiftMonth(1); });
  $('cal-today').addEventListener('click', function () {
    var n = new Date();
    view.y = n.getFullYear();
    view.m = n.getMonth();
    selected = todayKey();
    clearTaskError();
    renderCalendar();
  });

  $('cal-grid').addEventListener('click', function (e) {
    var btn = e.target.closest('button.cell');
    if (!btn || !btn.dataset.date) return;
    selected = btn.dataset.date;
    clearTaskError();
    renderCalendar();
  });

  $('task-form').addEventListener('submit', function (e) {
    e.preventDefault();
    var input = $('task-title');
    var title = input.value.trim();
    var err = $('task-error');
    input.classList.remove('invalid');
    err.textContent = '';
    if (!title) {
      err.textContent = 'Укажите, что запланировано: пустое название не сохраняется';
      input.classList.add('invalid');
      return;
    }
    if (title.length > MAX_TITLE) {
      err.textContent = 'Название дела не длиннее 60 символов';
      input.classList.add('invalid');
      return;
    }
    tasks.push({ id: newId(), date: selected, title: title, done: false });
    saveTasks();
    input.value = '';
    renderCalendar();
    input.focus();
  });

  $('day-list').addEventListener('change', function (e) {
    if (!e.target.classList.contains('task-done')) return;
    var li = e.target.closest('li.task');
    var id = li && li.dataset.id;
    tasks.forEach(function (t) {
      if (t.id === id) t.done = e.target.checked;
    });
    saveTasks();
    renderCalendar();
  });

  $('day-list').addEventListener('click', function (e) {
    var btn = e.target.closest('button.del');
    if (!btn) return;
    var id = btn.dataset.id;
    tasks = tasks.filter(function (t) { return t.id !== id; });
    saveTasks();
    renderCalendar();
  });

  $('task-title').addEventListener('input', clearTaskError);

  renderWallet();
  renderCalendar();
})();
