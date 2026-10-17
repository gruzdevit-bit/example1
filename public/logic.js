(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.WalletLogic = factory();
  }
}(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  var MAX_LABEL = 60;
  var STORAGE_KEY = 'wallet.operations.v1';
  var MINUS = '\u2212';
  var RUB = '\u20BD';

  var MSG_AMOUNT = 'Введите целую сумму от 1 ₽';
  var MSG_LABEL_EMPTY = 'Укажите, на что деньги: пустая подпись не сохраняется';
  var MSG_LABEL_LONG = 'Подпись не длиннее 60 символов';

  function validateAmount(raw) {
    var s = (raw === null || raw === undefined) ? '' : String(raw).trim();
    if (!/^\d+$/.test(s)) return { ok: false, error: MSG_AMOUNT };
    var n = Number(s);
    if (!Number.isSafeInteger(n) || n < 1) return { ok: false, error: MSG_AMOUNT };
    return { ok: true, value: n };
  }

  function validateLabel(raw) {
    var s = (raw === null || raw === undefined) ? '' : String(raw).trim();
    if (s.length === 0) return { ok: false, error: MSG_LABEL_EMPTY };
    if (Array.from(s).length > MAX_LABEL) return { ok: false, error: MSG_LABEL_LONG };
    return { ok: true, value: s };
  }

  function groupDigits(n) {
    return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  }

  // Сумма без знака плюс: «5 000 ₽», «−1 200 ₽», «0 ₽»
  function formatMoney(n) {
    var abs = Math.abs(n);
    return (n < 0 ? MINUS : '') + groupDigits(abs) + ' ' + RUB;
  }

  // Сумма операции со знаком: «+5 000 ₽», «−1 200 ₽»
  function formatSigned(amount, type) {
    return (type === 'income' ? '+' : MINUS) + groupDigits(Math.abs(amount)) + ' ' + RUB;
  }

  function pad2(n) { return (n < 10 ? '0' : '') + n; }

  function formatDate(value) {
    var d = value instanceof Date ? value : new Date(value);
    if (isNaN(d.getTime())) return '';
    return pad2(d.getDate()) + '.' + pad2(d.getMonth() + 1) + '.' + d.getFullYear();
  }

  function computeBalance(ops) {
    var sum = 0;
    for (var i = 0; i < ops.length; i++) {
      sum += ops[i].type === 'income' ? ops[i].amount : -ops[i].amount;
    }
    return sum;
  }

  // Новые сверху: хранится порядок добавления, выводим в обратном
  function newestFirst(ops) {
    return ops.slice().reverse();
  }

  var counter = 0;
  function makeId(now) {
    counter += 1;
    return String(now) + '-' + counter;
  }

  function isValidOperation(o) {
    return !!o && typeof o === 'object' &&
      typeof o.id === 'string' &&
      Number.isSafeInteger(o.amount) && o.amount >= 1 &&
      (o.type === 'income' || o.type === 'expense') &&
      typeof o.label === 'string' && o.label.length >= 1 &&
      typeof o.date === 'string' && !isNaN(new Date(o.date).getTime());
  }

  function parseStored(json) {
    if (typeof json !== 'string' || json === '') return [];
    var data;
    try { data = JSON.parse(json); } catch (e) { return []; }
    if (!Array.isArray(data)) return [];
    return data.filter(isValidOperation);
  }

  // Проверка и создание операции. Возвращает { ok, operation } или { ok:false, errors:{amount,label} }
  function buildOperation(input, now) {
    var date = now instanceof Date ? now : new Date();
    var a = validateAmount(input.amount);
    var l = validateLabel(input.label);
    var type = input.type === 'income' ? 'income' : 'expense';
    if (!a.ok || !l.ok) {
      var errors = {};
      if (!a.ok) errors.amount = a.error;
      if (!l.ok) errors.label = l.error;
      return { ok: false, errors: errors };
    }
    return {
      ok: true,
      operation: {
        id: makeId(date.getTime()),
        amount: a.value,
        type: type,
        label: l.value,
        date: date.toISOString()
      }
    };
  }

  return {
    STORAGE_KEY: STORAGE_KEY,
    MAX_LABEL: MAX_LABEL,
    MSG_AMOUNT: MSG_AMOUNT,
    MSG_LABEL_EMPTY: MSG_LABEL_EMPTY,
    MSG_LABEL_LONG: MSG_LABEL_LONG,
    validateAmount: validateAmount,
    validateLabel: validateLabel,
    formatMoney: formatMoney,
    formatSigned: formatSigned,
    formatDate: formatDate,
    computeBalance: computeBalance,
    newestFirst: newestFirst,
    parseStored: parseStored,
    buildOperation: buildOperation
  };
}));
