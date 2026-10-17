// Kill-switch service worker.
// If any stale service worker was ever registered on this origin, this file
// (served at /sw.js) replaces it, then unregisters itself and clears all caches
// so the app always loads fresh from the network. The SPA also calls
// navigator.serviceWorker.getRegistrations().unregister() on boot.
self.addEventListener('install', () => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      try {
        const keys = await caches.keys();
        await Promise.all(keys.map((k) => caches.delete(k)));
      } catch {
        /* ignore */
      }
      await self.registration.unregister();
      const clientsArr = await self.clients.matchAll({ type: 'window' });
      clientsArr.forEach((c) => c.navigate(c.url));
    })(),
  );
});
