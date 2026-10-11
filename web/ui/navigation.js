import animate from './motion.js';

function refresh() {
  document.querySelectorAll('.nav button.active, .switch button.active, .inbox-tabs button.active').forEach(button => {
    if (button.querySelector('.nav-indicator')) return;
    const indicator = document.createElement('span');
    indicator.className = 'nav-indicator';
    indicator.setAttribute('aria-hidden', 'true');
    button.append(indicator);
    animate(indicator, [
      { transform: 'scaleX(0)' },
      { transform: 'scaleX(1)' },
    ], 'slide');
  });
}

function enterPage() {
  const main = document.querySelector('#main');
  if (main) animate(main, [{ opacity: 0, transform: 'translateY(12px)' }, { opacity: 1, transform: 'none' }], 'slide');
}

export default { refresh, enterPage };
