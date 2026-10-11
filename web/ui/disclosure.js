import animate from './motion.js';
import icon from './icons.js';

const enhanced = new WeakSet();

export default function enhanceDisclosure(details) {
  if (enhanced.has(details)) return;
  enhanced.add(details);
  const summary = details.querySelector(':scope > summary');
  if (!summary) return;
  summary.append(icon('chevron'));
  const body = wrapContent(details, summary);
  let animation;
  let expanded = details.open;
  summary.setAttribute('aria-expanded', String(expanded));
  summary.addEventListener('click', event => {
    event.preventDefault();
    const start = details.open ? body.getBoundingClientRect().height : 0;
    animation?.cancel();
    expanded = !expanded;
    details.open = true;
    summary.setAttribute('aria-expanded', String(expanded));
    animation = animate(body, [{ height: `${start}px` }, { height: `${expanded ? body.scrollHeight : 0}px` }]);
    animation.onfinish = () => { details.open = expanded; };
  });
  details.addEventListener('toggle', () => {
    if (animation?.playState !== 'running') expanded = details.open;
    summary.setAttribute('aria-expanded', String(expanded));
  });
}

function wrapContent(details, summary) {
  const body = document.createElement('div');
  body.className = 'disclosure-body';
  const inner = document.createElement('div');
  inner.className = 'disclosure-inner';
  Array.from(details.childNodes).filter(node => node !== summary).forEach(node => inner.append(node));
  body.append(inner);
  details.append(body);
  return body;
}
