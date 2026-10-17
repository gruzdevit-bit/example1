'use strict';

const test = require('node:test');
const assert = require('node:assert');
const L = require('../public/logic.js');

test('validateAmount: корректные суммы', () => {
  assert.deepStrictEqual(L.validateAmount('5000'), { ok: true, value: 5000 });
  assert.deepStrictEqual(L.validateAmount(' 1 '), { ok: true, value: 1 });
  assert.deepStrictEqual(L.validateAmount('1000000'), { ok: true, value: 1000000 });
});

test('validateAmount: 0, отрицательное, дробное, пустое, мусор', () => {
  for (const raw of ['0', '-50', '10.5', '10,5', '', '   ', 'abc', '1e3', null, undefined]) {
    const r = L.validateAmount(raw);
    assert.strictEqual(r.ok, false, String(raw));
    assert.strictEqual(r.error, 'Введите целую сумму от 1 ₽');
  }
});

test('validateLabel: пустая и из пробелов', () => {
  assert.strictEqual(L.validateLabel('').ok, false);
  assert.strictEqual(L.validateLabel('     ').ok, false);
  assert.match(L.validateLabel('').error, /подпись/);
});

test('validateLabel: обрезка пробелов', () => {
  assert.deepStrictEqual(L.validateLabel('  Кофе  '), { ok: true, value: 'Кофе' });
});

test('validateLabel: 60 допустимо, 61 нет', () => {
  assert.strictEqual(L.validateLabel('а'.repeat(60)).ok, true);
  const r = L.validateLabel('а'.repeat(61));
  assert.strictEqual(r.ok, false);
  assert.strictEqual(r.error, 'Подпись не длиннее 60 символов');
});

test('formatMoney', () => {
  assert.strictEqual(L.formatMoney(0), '0 ₽');
  assert.strictEqual(L.formatMoney(5000), '5 000 ₽');
  assert.strictEqual(L.formatMoney(3800), '3 800 ₽');
  assert.strictEqual(L.formatMoney(-1200), '\u22121 200 ₽');
  assert.strictEqual(L.formatMoney(1000000), '1 000 000 ₽');
});

test('formatSigned', () => {
  assert.strictEqual(L.formatSigned(5000, 'income'), '+5 000 ₽');
  assert.strictEqual(L.formatSigned(1200, 'expense'), '\u22121 200 ₽');
  assert.strictEqual(L.formatSigned(5000, 'expense'), '\u22125 000 ₽');
  assert.strictEqual(L.formatSigned(1000000, 'income'), '+1 000 000 ₽');
});

test('formatDate: ДД.ММ.ГГГГ', () => {
  assert.strictEqual(L.formatDate(new Date(2025, 4, 5, 10, 0, 0)), '05.05.2025');
  assert.strictEqual(L.formatDate(new Date(2024, 11, 31, 23, 59, 0)), '31.12.2024');
  assert.strictEqual(L.formatDate('не дата'), '');
});

test('сценарий тест-кейсов 2-4: остаток и порядок', () => {
  const ops = [];
  const add = (amount, label, type) => {
    const r = L.buildOperation({ amount, label, type }, new Date(2025, 4, 14, 12, 0, 0));
    assert.strictEqual(r.ok, true);
    ops.push(r.operation);
  };
  assert.strictEqual(L.computeBalance(ops), 0);
  add('5000', 'Зарплата', 'income');
  assert.strictEqual(L.formatMoney(L.computeBalance(ops)), '5 000 ₽');
  add('1200', 'Продукты', 'expense');
  assert.strictEqual(L.formatMoney(L.computeBalance(ops)), '3 800 ₽');
  assert.deepStrictEqual(L.newestFirst(ops).map(o => o.label), ['Продукты', 'Зарплата']);
  add('5000', 'Ремонт', 'expense');
  assert.strictEqual(L.computeBalance(ops), -1200);
  assert.strictEqual(L.formatMoney(L.computeBalance(ops)), '\u22121 200 ₽');
  assert.deepStrictEqual(L.newestFirst(ops).map(o => o.label), ['Ремонт', 'Продукты', 'Зарплата']);
  assert.strictEqual(L.formatDate(ops[0].date), '14.05.2025');
});

test('buildOperation: ошибки не создают операцию', () => {
  const empty = L.buildOperation({ amount: '100', label: '', type: 'expense' });
  assert.strictEqual(empty.ok, false);
  assert.ok(empty.errors.label);
  assert.strictEqual(empty.errors.amount, undefined);

  const spaces = L.buildOperation({ amount: '100', label: '   ', type: 'expense' });
  assert.strictEqual(spaces.ok, false);
  assert.ok(spaces.errors.label);

  const zero = L.buildOperation({ amount: '0', label: 'Тест', type: 'expense' });
  assert.strictEqual(zero.ok, false);
  assert.strictEqual(zero.errors.amount, 'Введите целую сумму от 1 ₽');

  const long = L.buildOperation({ amount: '100', label: 'ж'.repeat(61), type: 'expense' });
  assert.strictEqual(long.ok, false);
  assert.strictEqual(long.errors.label, 'Подпись не длиннее 60 символов');
});

test('buildOperation: подпись обрезается, тип по умолчанию расход', () => {
  const r = L.buildOperation({ amount: '100', label: '  Кофе  ', type: 'expense' });
  assert.strictEqual(r.ok, true);
  assert.strictEqual(r.operation.label, 'Кофе');
  assert.strictEqual(r.operation.type, 'expense');
  assert.strictEqual(r.operation.amount, 100);
  const d = L.buildOperation({ amount: '5', label: 'x' });
  assert.strictEqual(d.operation.type, 'expense');
});

test('id операций уникальны', () => {
  const now = new Date();
  const a = L.buildOperation({ amount: '1', label: 'a', type: 'income' }, now).operation;
  const b = L.buildOperation({ amount: '1', label: 'b', type: 'income' }, now).operation;
  assert.notStrictEqual(a.id, b.id);
});

test('parseStored: повреждённые данные дают пустой кошелёк', () => {
  assert.deepStrictEqual(L.parseStored(null), []);
  assert.deepStrictEqual(L.parseStored(''), []);
  assert.deepStrictEqual(L.parseStored('{oops'), []);
  assert.deepStrictEqual(L.parseStored('{"a":1}'), []);
  assert.deepStrictEqual(L.parseStored('[{"id":"1","amount":0,"type":"income","label":"x","date":"2025-05-01T00:00:00.000Z"}]'), []);
});

test('parseStored: валидные записи сохраняются, мусор отбрасывается', () => {
  const good = { id: '1', amount: 10, type: 'income', label: 'x', date: '2025-05-01T00:00:00.000Z' };
  const json = JSON.stringify([good, null, { amount: 'a' }]);
  assert.deepStrictEqual(L.parseStored(json), [good]);
});

test('сохранение и загрузка: порядок не теряется (тест-кейс 14)', () => {
  const ops = ['a', 'b', 'c'].map(l => L.buildOperation({ amount: '10', label: l, type: 'income' }).operation);
  const restored = L.parseStored(JSON.stringify(ops));
  assert.deepStrictEqual(L.newestFirst(restored).map(o => o.label), ['c', 'b', 'a']);
  assert.strictEqual(L.computeBalance(restored), 30);
});
