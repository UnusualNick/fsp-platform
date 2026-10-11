const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
const timings = {
  layer: { duration: 300, easing: 'cubic-bezier(.33, 1, .68, 1)' },
  slide: { duration: 300, easing: 'cubic-bezier(.25, 1, .5, 1)' },
  menu: { duration: 150, easing: 'cubic-bezier(.2, 0, .2, 1)' },
  menuClose: { duration: 200, easing: 'ease-in' },
  modal: { duration: 200, easing: 'ease' },
};

export default function animate(element, keyframes, preset = 'layer') {
  return element.animate(keyframes, {
    ...timings[preset], duration: reducedMotion.matches ? 0 : timings[preset].duration,
  });
}
