// Shortlist ("♡", from paavai-embroidery-web): item codes the visitor saved, kept in this browser only
// (localStorage). Every [data-heart="PE-0001"] button toggles a code; every
// [data-shortlist-count] shows how many are saved; [data-shortlist-float]
// appears once something is saved.
import { sendServerEvent, trackEvent } from './tracking';
import { countDesign } from './stats';

const KEY = `${(import.meta.env.PUBLIC_SITE_KEY as string | undefined) || 'site'}-shortlist`;
const MAX = 60;

export function getShortlist(): string[] {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) || '[]');
    return Array.isArray(v) ? v.filter((x): x is string => typeof x === 'string') : [];
  } catch {
    return [];
  }
}

export function setShortlist(codes: string[]) {
  const list = [...new Set(codes.map((c) => c.toUpperCase()))].slice(-MAX);
  try {
    localStorage.setItem(KEY, JSON.stringify(list));
  } catch {
    /* private mode: the list lasts for this page only */
  }
  window.dispatchEvent(new CustomEvent('shortlist:change', { detail: list }));
}

export function addToShortlist(codes: string[]) {
  const list = getShortlist();
  const added = codes.map((c) => c.toUpperCase()).filter((c) => !list.includes(c));
  setShortlist([...list, ...added]);
  added.forEach((c) => countDesign(c, 'shortlist'));
  if (added.length) {
    const product = { content_ids: added, content_type: 'product' as const };
    sendServerEvent('AddToWishlist', trackEvent('AddToWishlist', product), product);
  }
}

export function toggleShortlist(code: string) {
  const list = getShortlist();
  if (list.includes(code)) setShortlist(list.filter((c) => c !== code));
  else addToShortlist([code]);
}

function render() {
  const list = getShortlist();
  document.querySelectorAll<HTMLElement>('[data-heart]').forEach((b) => {
    const on = list.includes(b.dataset.heart!);
    b.setAttribute('aria-pressed', String(on));
    const label = b.querySelector<HTMLElement>('[data-heart-label]');
    if (label) label.textContent = on ? b.dataset.labelOn! : b.dataset.labelOff!;
  });
  document.querySelectorAll<HTMLElement>('[data-shortlist-count]').forEach((el) => (el.textContent = String(list.length)));
  document.querySelectorAll<HTMLElement>('[data-shortlist-float]').forEach((el) => (el.hidden = list.length === 0));
}

export function initShortlist() {
  document.addEventListener('click', (e) => {
    const btn = (e.target as Element | null)?.closest<HTMLElement>('[data-heart]');
    if (!btn) return;
    e.preventDefault();
    e.stopPropagation();
    toggleShortlist(btn.dataset.heart!);
  });
  window.addEventListener('shortlist:change', render);
  window.addEventListener('storage', (e) => e.key === KEY && render());
  render();
}
