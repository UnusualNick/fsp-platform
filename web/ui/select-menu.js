import animate from './motion.js';

let activeMenu;

export default function createMenu(trigger, menu) {
  let opened = false;
  let animation;
  let controller;
  const close = () => {
    if (!opened) return;
    opened = false;
    menu.style.pointerEvents = 'none';
    trigger.setAttribute('aria-expanded', 'false');
    trigger.removeAttribute('aria-activedescendant');
    animation?.cancel();
    animation = animate(menu, [{ opacity: 1 }, { opacity: 0 }], 'menuClose');
    animation.onfinish = () => { if (!opened) menu.hidePopover(); };
    controller?.abort();
    if (activeMenu === close) activeMenu = undefined;
  };
  const open = () => {
    if (opened) return;
    activeMenu?.();
    activeMenu = close;
    animation?.cancel();
    menu.showPopover();
    menu.style.pointerEvents = '';
    opened = true;
    trigger.setAttribute('aria-expanded', 'true');
    positionMenu(trigger, menu);
    animation = animate(menu, [{ opacity: 0, transform: 'scale(.85)' },
      { opacity: 1, transform: 'scale(1)' }], 'menu');
    controller = bindDismissal(trigger, menu, close);
  };
  return { open, close, isOpen: () => opened };
}

function positionMenu(trigger, menu) {
  const rect = trigger.getBoundingClientRect();
  const margin = 8;
  const bottomSpace = innerHeight - rect.bottom - margin;
  const above = bottomSpace < 180 && rect.top > bottomSpace;
  menu.style.width = `${Math.min(Math.max(rect.width, 148), innerWidth - margin * 2)}px`;
  menu.style.maxHeight = `${Math.min(320, Math.max(80, above ? rect.top - 16 : bottomSpace - 8))}px`;
  menu.style.left = `${Math.max(margin, Math.min(rect.left, innerWidth - menu.offsetWidth - margin))}px`;
  menu.style.top = `${above ? rect.top - menu.offsetHeight - 8 : rect.bottom + 8}px`;
  menu.style.transformOrigin = above ? 'bottom center' : 'top center';
}

function bindDismissal(trigger, menu, close) {
  const controller = new AbortController();
  const options = { signal: controller.signal, capture: true };
  document.addEventListener('pointerdown', event => {
    if (!trigger.contains(event.target) && !menu.contains(event.target)) close();
  }, options);
  document.addEventListener('scroll', event => {
    if (!menu.contains(event.target)) close();
  }, options);
  window.addEventListener('resize', close, options);
  document.addEventListener('focusin', event => {
    if (!trigger.contains(event.target) && !menu.contains(event.target)) close();
  }, options);
  return controller;
}
