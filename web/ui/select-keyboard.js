export default function bindKeyboard(control) {
  let phrase = '';
  let lastTyped = 0;
  control.trigger.addEventListener('keydown', event => {
    const key = event.key;
    if (key === 'Tab') return control.close();
    if (key === 'Escape' && control.isOpen()) {
      event.preventDefault();
      event.stopPropagation();
      return control.close();
    }
    if (['ArrowDown', 'ArrowUp', 'Home', 'End', 'Enter', ' '].includes(key)) {
      event.preventDefault();
      return navigate(control, key);
    }
    if (key.length !== 1 || event.ctrlKey || event.metaKey || event.altKey) return;
    event.preventDefault();
    phrase = Date.now() - lastTyped > 700 ? key : phrase + key;
    lastTyped = Date.now();
    control.open();
    control.match(phrase);
  });
}

function navigate(control, key) {
  if (key === 'Enter' || key === ' ') {
    return control.isOpen() ? control.choose() : control.open();
  }
  control.open();
  const actions = { ArrowDown: 1, ArrowUp: -1, Home: 'first', End: 'last' };
  control.move(actions[key]);
}
