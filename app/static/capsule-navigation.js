'use strict';
(() => {
 const routes = new Set(['/home', '/account', '/admin']);
 let request, sequence = 0;
 const observed = new WeakSet();
 const activeLink = () => document.querySelector('.primary-capsule a[aria-current=page]');
 function place(link, animate = true) {
  const capsule = link?.closest('.primary-capsule');
  if (!capsule) return;
  if (!animate) delete capsule.dataset.sliderAnimate;
  capsule.style.setProperty('--nav-x', link.offsetLeft + 'px');
  capsule.style.setProperty('--nav-y', link.offsetTop + 'px');
  capsule.style.setProperty('--nav-width', link.offsetWidth + 'px');
  capsule.style.setProperty('--nav-height', link.offsetHeight + 'px');
  capsule.dataset.sliderReady = 'true';
  requestAnimationFrame(() => { capsule.dataset.sliderAnimate = 'true'; });
 }
 function bind() {
  for (const capsule of document.querySelectorAll('.primary-capsule')) {
   place(capsule.querySelector('[aria-current=page]'), observed.has(capsule));
   if (!observed.has(capsule)) {
    observed.add(capsule);
    const observer = new ResizeObserver(() => place(capsule.querySelector('[aria-current=page]'), false));
    observer.observe(capsule);
   }
  }
 }
 function select(path) {
  const capsule = document.querySelector('.primary-capsule:not(.guest-primary-capsule)');
  if (!capsule) return;
  for (const link of capsule.querySelectorAll('a')) {
   const selected = link.pathname === '/admin' ? path.startsWith('/admin') : link.pathname === path;
   if (selected) { link.setAttribute('aria-current', 'page'); place(link); }
   else link.removeAttribute('aria-current');
  }
 }
 const eligible = url => url.origin === location.origin && routes.has(url.pathname) && !url.search;
 function syncStyles(doc) {
  const next = [...doc.querySelectorAll('head link[rel=stylesheet]')];
  const wanted = new Set(next.map(link => new URL(link.getAttribute('href'), location.origin).href));
  for (const current of document.querySelectorAll('head link[rel=stylesheet]')) {
   // The live appearance sheet may have a cache-busting URL after changing mode.
   if (new URL(current.href).pathname !== '/theme.css' && !wanted.has(current.href)) current.remove();
  }
  for (const link of next) {
   const href = new URL(link.getAttribute('href'), location.origin);
   if (href.origin !== location.origin) continue;
   if ([...document.querySelectorAll('head link[rel=stylesheet]')].some(current =>
    current.href === href.href || (href.pathname === '/theme.css' && new URL(current.href).pathname === '/theme.css'))) continue;
   document.head.append(document.importNode(link, true));
  }
 }
 async function navigate(url, fromHistory = false) {
  request?.abort(); request = new AbortController();
  const id = ++sequence, main = document.querySelector('.shell > main');
  const previous = location.pathname;
  if (!main) { location.assign(url.href); return; }
  main.querySelector('.capsule-load-error')?.remove();
  main.setAttribute('aria-busy', 'true');
  select(url.pathname);
  try {
   const response = await fetch(url.href, {credentials:'same-origin', cache:'no-store', signal:request.signal, headers:{Accept:'text/html'}});
   if (id !== sequence) return;
   const destination = new URL(response.url);
   if (!eligible(destination)) { location.assign(destination.href); return; }
   if (!response.ok || !response.headers.get('content-type')?.includes('text/html')) throw Error();
   const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
   if (id !== sequence) return;
   const nextMain = doc.querySelector('.shell > main');
   const nextHeader = doc.querySelector('.topbar-modern');
   // A missing authenticated header means the session or installation state changed.
   if (!nextMain || doc.body.dataset.authenticated !== 'true') {
    location.assign(destination.href); return;
   }
   const header = document.querySelector('.topbar-modern');
   const capsule = header?.querySelector('.primary-capsule');
   const nextCapsule = nextHeader?.querySelector('.primary-capsule');
   if (capsule && nextCapsule) {
    for (const link of capsule.querySelectorAll('a')) {
     const fresh = [...nextCapsule.querySelectorAll('a')].find(item => item.pathname === link.pathname);
     if (!fresh) { link.remove(); continue; }
     link.replaceChildren(...fresh.childNodes);
     link.setAttribute('aria-label', fresh.getAttribute('aria-label'));
    }
    for (const fresh of nextCapsule.querySelectorAll('a')) {
     if (![...capsule.querySelectorAll('a')].some(link => link.pathname === fresh.pathname)) capsule.append(fresh);
    }
   }
   syncStyles(doc);
   if (header && nextHeader && capsule && nextCapsule) {
    // Keep the capsule connected so its in-flight sliding transition survives.
    for (const selector of [':scope > .brand', ':scope > .account-menu']) {
     const oldPart = header.querySelector(selector), newPart = nextHeader.querySelector(selector);
     if (oldPart) newPart ? oldPart.replaceWith(newPart) : oldPart.remove();
     else if (newPart) header.append(newPart);
    }
    header.className = nextHeader.className;
   } else if (header) nextHeader ? header.replaceWith(nextHeader) : header.remove();
   else if (nextHeader) document.querySelector('.shell').prepend(nextHeader);
   main.replaceWith(nextMain);
   const footer = document.querySelector('.shell > .global-footer');
   const nextFooter = doc.querySelector('.shell > .global-footer');
   if (footer) nextFooter ? footer.replaceWith(nextFooter) : footer.remove();
   else if (nextFooter) document.querySelector('.shell').append(nextFooter);
   document.title = doc.title;
   document.documentElement.lang = doc.documentElement.lang;
   if (doc.documentElement.dir) document.documentElement.dir = doc.documentElement.dir;
   else document.documentElement.removeAttribute('dir');
   for (const key of ['accent','button_hover','bg','surface','text','muted','ink','logo-filter','default-brand-logo']) document.documentElement.style.removeProperty('--' + key);
   document.documentElement.style.removeProperty('color-scheme');
   document.body.className = doc.body.className;
   if (doc.body.hasAttribute('style')) document.body.setAttribute('style', doc.body.getAttribute('style'));
   else document.body.removeAttribute('style');
   for (const key of ['saving','saved','failed']) document.body.dataset[key] = doc.body.dataset[key] || '';
   if (!fromHistory) {
    history.replaceState({...history.state, capsuleScroll:[scrollX,scrollY]}, '');
    history.pushState({capsuleNavigation:true}, '', destination.href);
   }
   select(destination.pathname);
   document.dispatchEvent(new CustomEvent('gatearr:headerupdated'));
   document.dispatchEvent(new CustomEvent('gatearr:navigated', {detail:{url:destination.href}}));
   const heading = nextMain.querySelector('h1');
   if (heading) { heading.setAttribute('tabindex','-1'); heading.focus({preventScroll:true}); }
   const position = fromHistory ? history.state?.capsuleScroll || [0,0] : [0,0];
   window.scrollTo(...position);
  } catch (error) {
   if (error.name === 'AbortError' || id !== sequence) return;
   select(previous);
   if (fromHistory) { location.reload(); return; }
   const notice = document.createElement('p');
   notice.className = 'capsule-load-error'; notice.setAttribute('role','alert');
   notice.textContent = document.body.dataset.failed || 'Failed';
   main.prepend(notice);
  } finally {
   if (id === sequence) { request = null; document.querySelector('.shell > main')?.removeAttribute('aria-busy'); }
  }
 }
 document.addEventListener('click', event => {
  const link = event.target.closest('.primary-capsule:not(.guest-primary-capsule) a, .admin-mosaic-heading a[href="/home"]');
  if (!link || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || link.target || link.hasAttribute('download')) return;
  const url = new URL(link.href);
  if (!eligible(url)) return;
  event.preventDefault();
  if (url.href === location.href && !request) return;
  navigate(url);
 });
 window.addEventListener('popstate', () => {
  const url = new URL(location.href);
  if (eligible(url) && document.querySelector('.primary-capsule:not(.guest-primary-capsule)')) navigate(url, true);
  else location.reload();
 });
 document.addEventListener('gatearr:headerupdated', bind);
 window.addEventListener('pageshow', bind);
 document.fonts?.ready.then(bind);
 bind();
})();
