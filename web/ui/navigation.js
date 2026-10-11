import animate from './motion.js';

let previous;

function capture() {
  const indicator = document.querySelector('.nav .nav-indicator');
  previous = indicator?.getBoundingClientRect();
}

function refresh() {
  document.querySelectorAll('.nav button.active, .switch button.active, .inbox-tabs button.active').forEach(button => {
    if (button.querySelector('.nav-indicator')) return;
    const indicator = document.createElement('span');
    indicator.className = 'nav-indicator';
    indicator.setAttribute('aria-hidden', 'true');
    button.append(indicator);
    if (!button.closest('.nav') || !previous) return;
    const current = indicator.getBoundingClientRect();
    animate(indicator, [
      { transform: `translate(${previous.x - current.x}px, ${previous.y - current.y}px)`
        + ` scaleX(${previous.width / current.width})` },
      { transform: 'translate(0, 0) scaleX(1)' },
    ], 'slide');
    previous = undefined;
  });
}

function enterPage() {
  const main = document.querySelector('#main');
  if (main) animate(main, [{ opacity: 0, transform: 'translateY(12px)' }, { opacity: 1, transform: 'none' }], 'slide');
}

export default { capture, refresh, enterPage };
