(function () {
  'use strict';

  var L = window.WalletLogic;

  var els = {
    form: document.getElementById('form'),
    amount: document.getElementById('amount'),
    label: document.getElementById('label'),
    amountError: document.getElementById('amount-error'),
    amountHint: document.getElementById('amount-hint'),
    labelError: document.getElementById('label-error'),
    balance: document.getElementById('balance'),
    list: document.getElementById('list'),
    empty: document.getElementById('empty')
  };

  var operations = [];
  var memoryOnly = false;

  function load() {
    try {
      return L.parseStored(window.localStorage.getItem(L.STORAGE_KEY));
    } catch (e) {
      memoryOnly = true;
      return [];
    }
  }

  function save() {
    if (memoryOnly) return;
    try {
      window.localStorage.setItem(L.STORAGE_KEY, JSON.stringify(operations));
    } catch (e) {
      memoryOnly = true;
    }
  }

  function render() {
    var bal = L.computeBalance(operations);
    els.balance.textContent = L.formatMoney(bal);
    els.balance.classList.toggle('negative', bal < 0);

    els.list.textContent = '';
    if (operations.length === 0) {
      els.list.hidden = true;
      els.empty.hidden = false;
      return;
    }
    els.empty.hidden = true;
    els.list.hidden = false;

    L.newestFirst(operations).forEach(function (op) {
      var li = document.createElement('li');
      var date = document.createElement('span');
      date.className = 'date';
      date.textContent = L.formatDate(op.date);
      var name = document.createElement('span');
      name.className = 'name';
      name.textContent = op.label;
      var amt = document.createElement('span');
      amt.className = 'amt ' + (op.type === 'income' ? 'plus' : 'minus');
      amt.textContent = L.formatSigned(op.amount, op.type);
      li.appendChild(date);
      li.appendChild(name);
      li.appendChild(amt);
      els.list.appendChild(li);
    });
  }

  function showErrors(errors) {
    if (errors.amount) {
      els.amount.classList.add('err');
      els.amountError.textContent = errors.amount;
      els.amountError.hidden = false;
      els.amountHint.hidden = true;
    }
    if (errors.label) {
      els.label.classList.add('err');
      els.labelError.textContent = errors.label;
      els.labelError.hidden = false;
    }
  }

  function clearErrors() {
    els.amount.classList.remove('err');
    els.label.classList.remove('err');
    els.amountError.hidden = true;
    els.amountError.textContent = '';
    els.labelError.hidden = true;
    els.labelError.textContent = '';
    els.amountHint.hidden = false;
  }

  function selectedType() {
    var checked = els.form.querySelector('input[name="type"]:checked');
    return checked ? checked.value : 'expense';
  }

  els.form.addEventListener('submit', function (ev) {
    ev.preventDefault();
    clearErrors();
    var result = L.buildOperation({
      amount: els.amount.value,
      label: els.label.value,
      type: selectedType()
    }, new Date());

    if (!result.ok) {
      showErrors(result.errors);
      return;
    }
    operations.push(result.operation);
    save();
    render();
    els.amount.value = '';
    els.label.value = '';
    els.amount.focus();
  });

  els.amount.addEventListener('input', function () {
    els.amount.classList.remove('err');
    els.amountError.hidden = true;
    els.amountHint.hidden = false;
  });
  els.label.addEventListener('input', function () {
    els.label.classList.remove('err');
    els.labelError.hidden = true;
  });

  operations = load();
  render();
}());
