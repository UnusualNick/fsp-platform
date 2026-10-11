import animate from './motion.js';

let timer;
let animation;

export default function showToast(message) {
  const toast = document.querySelector('#toast');
  clearTimeout(timer);
  animation?.cancel();
  toast.textContent = message;
  toast.style.display = 'block';
  animation = animate(toast, [{ opacity: 0, translate: '0 12px' }, { opacity: 1, translate: '0 0' }]);
  timer = setTimeout(() => {
    animation = animate(toast, [{ opacity: 1 }, { opacity: 0 }], 'modal');
    animation.onfinish = () => { toast.style.display = 'none'; };
  }, 6000);
}
