import animate from './motion.js';

const modal = document.querySelector('#modal');
let animation;
let pressedBackdrop = false;

function open(content) {
  animation?.cancel();
  pressedBackdrop = false;
  document.querySelector('#modal-content').innerHTML = content;
  scopeFieldIds();
  if (!modal.open) modal.showModal();
  modal.scrollTop = 0;
  modal.querySelector('[data-close]')?.focus({ preventScroll: true });
  animation = animate(modal, [{ opacity: 0, transform: 'translateY(-16px)' },
    { opacity: 1, transform: 'translateY(0)' }], 'modal');
  modal.querySelector('[data-close]')?.addEventListener('click', close);
}

function close() {
  if (!modal.open) return;
  animation?.cancel();
  animation = animate(modal, [{ opacity: 1, transform: 'translateY(0)' },
    { opacity: 0, transform: 'translateY(16px)' }], 'modal');
  animation.onfinish = () => {
    modal.close();
    document.querySelector('#modal-content').replaceChildren();
  };
}

function scopeFieldIds() {
  modal.querySelectorAll('input[id], select[id], textarea[id]').forEach(field => {
    const label = modal.querySelector(`label[for="${field.id}"]`);
    field.id = `dialog-${field.id}`;
    if (label) label.htmlFor = field.id;
  });
}

function isBackdrop(event) {
  if (event.target !== modal) return false;
  const bounds = modal.getBoundingClientRect();
  return event.clientX < bounds.left || event.clientX > bounds.right
    || event.clientY < bounds.top || event.clientY > bounds.bottom;
}

modal.addEventListener('pointerdown', event => {
  pressedBackdrop = event.button === 0 && isBackdrop(event);
});
modal.addEventListener('pointercancel', () => { pressedBackdrop = false; });
modal.addEventListener('click', event => {
  if (pressedBackdrop && isBackdrop(event)) close();
  pressedBackdrop = false;
});
modal.addEventListener('cancel', event => { event.preventDefault(); close(); });

export default { open, close };
