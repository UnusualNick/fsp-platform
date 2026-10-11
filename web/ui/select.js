import icon from './icons.js';
import createMenu from './select-menu.js';
import bindKeyboard from './select-keyboard.js';

const controls = new WeakMap();
let sequence = 0;

export default function enhanceSelect(select) {
  if (controls.has(select)) return controls.get(select).sync();
  const elements = createElements(select);
  const menu = createMenu(elements.trigger, elements.menu);
  const control = createController(select, elements, menu);
  controls.set(select, control);
  bindKeyboard(control);
  bindEvents(select, elements, control);
  control.sync();
}

function createElements(select) {
  const wrapper = wrapNativeSelect(select);
  const trigger = document.createElement('button');
  trigger.type = 'button';
  trigger.className = 'select-trigger';
  trigger.id = `select-trigger-${++sequence}`;
  const value = document.createElement('span');
  value.className = 'select-value';
  trigger.append(value, icon('chevron'));
  const menu = makeList(select, trigger);
  wrapper.append(trigger, menu);
  labelTrigger(select, trigger);
  return { trigger, menu, value };
}

function wrapNativeSelect(select) {
  const wrapper = document.createElement('div');
  wrapper.className = 'select-control';
  select.before(wrapper);
  wrapper.append(select);
  select.classList.add('enhanced-select');
  select.hidden = true;
  select.tabIndex = -1;
  select.setAttribute('aria-hidden', 'true');
  return wrapper;
}

function makeList(select, trigger) {
  const menu = document.createElement('div');
  menu.className = 'select-menu';
  menu.id = `select-menu-${sequence}`;
  menu.setAttribute('popover', 'manual');
  menu.setAttribute('role', 'listbox');
  menu.setAttribute('aria-labelledby', trigger.id);
  trigger.setAttribute('role', 'combobox');
  trigger.setAttribute('aria-haspopup', 'listbox');
  trigger.setAttribute('aria-controls', menu.id);
  trigger.setAttribute('aria-expanded', 'false');
  Array.from(select.options).forEach((option, index) => menu.append(makeOption(option, menu.id, index)));
  return menu;
}

function makeOption(option, prefix, index) {
  const row = document.createElement('div');
  row.className = 'select-option';
  row.id = `${prefix}-${index}`;
  row.dataset.index = String(index);
  row.setAttribute('role', 'option');
  row.setAttribute('aria-disabled', String(option.disabled));
  const label = document.createElement('span');
  label.className = 'option-label';
  label.textContent = option.textContent;
  row.append(label, icon('check'));
  return row;
}

function labelTrigger(select, trigger) {
  const label = select.labels?.[0];
  if (label) {
    label.id ||= `${trigger.id}-label`;
    trigger.setAttribute('aria-labelledby', `${label.id} ${trigger.id}`);
    label.addEventListener('click', event => { event.preventDefault(); trigger.focus(); });
  } else {
    trigger.setAttribute('aria-label', select.getAttribute('aria-label') || select.name);
  }
}

function createController(select, elements, menu) {
  const rows = Array.from(elements.menu.children);
  let active = select.selectedIndex;
  const highlight = index => {
    if (!rows[index] || select.options[index].disabled) return;
    active = index;
    rows.forEach((row, rowIndex) => { row.dataset.active = String(rowIndex === index); });
    elements.trigger.setAttribute('aria-activedescendant', rows[index].id);
    rows[index].scrollIntoView({ block: 'nearest' });
  };
  const sync = () => {
    const text = select.selectedOptions[0]?.textContent || '';
    if (elements.value.textContent !== text) elements.value.textContent = text;
    elements.trigger.disabled = select.disabled;
    rows.forEach((row, index) => row.setAttribute('aria-selected', String(index === select.selectedIndex)));
  };
  const choose = () => {
    select.selectedIndex = active;
    sync();
    menu.close();
    select.dispatchEvent(new Event('change', { bubbles: true }));
  };
  return buildActions({ select, elements, menu, rows, highlight, sync, choose, active: () => active });
}

function buildActions(context) {
  const { select, elements, menu, rows, highlight } = context;
  return {
    ...menu, trigger: elements.trigger, sync: context.sync, choose: context.choose, highlight,
    open() { if (!menu.isOpen()) { menu.open(); highlight(select.selectedIndex); } },
    move(direction) {
      const enabled = rows.map((_, index) => index).filter(index => !select.options[index].disabled);
      const offset = enabled.indexOf(context.active());
      const index = direction === 'first' ? 0 : direction === 'last' ? enabled.length - 1 : offset + direction;
      highlight(enabled[Math.max(0, Math.min(enabled.length - 1, index))]);
    },
    match(phrase) {
      const index = Array.from(select.options).findIndex(option =>
        !option.disabled && option.text.toLocaleLowerCase().startsWith(phrase.toLocaleLowerCase()));
      if (index >= 0) highlight(index);
    },
  };
}

function bindEvents(select, elements, control) {
  elements.trigger.addEventListener('click', () => control.isOpen() ? control.close() : control.open());
  elements.menu.addEventListener('pointerdown', event => event.preventDefault());
  elements.menu.addEventListener('pointermove', event => {
    const row = event.target.closest('[role=option]');
    if (row) control.highlight(Number(row.dataset.index));
  });
  elements.menu.addEventListener('click', event => {
    const row = event.target.closest('[role=option]');
    if (!row || row.getAttribute('aria-disabled') === 'true') return;
    control.highlight(Number(row.dataset.index));
    control.choose();
  });
  select.addEventListener('change', control.sync);
  select.addEventListener('invalid', event => { event.preventDefault(); elements.trigger.focus(); });
  select.form?.addEventListener('reset', () => requestAnimationFrame(control.sync));
}
