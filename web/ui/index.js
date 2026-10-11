import enhanceSelect from './select.js';
import enhanceDisclosure from './disclosure.js';
import navigation from './navigation.js';

function refresh(root = document) {
  root.querySelectorAll('select').forEach(enhanceSelect);
  root.querySelectorAll('details').forEach(enhanceDisclosure);
  navigation.refresh();
}

let scheduled = false;
const observer = new MutationObserver(records => {
  if (scheduled || !records.some(record => record.addedNodes.length)) return;
  scheduled = true;
  queueMicrotask(() => { scheduled = false; refresh(); });
});
observer.observe(document.querySelector('#app'), { childList: true, subtree: true });
observer.observe(document.querySelector('#modal-content'), { childList: true, subtree: true });

export default refresh;
