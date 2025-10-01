// Simple offline queue for POST/PATCH requests when offline
(function(){
  const Q_KEY = 'ucs_offline_queue_v1';
  const loadQ = () => { try { return JSON.parse(localStorage.getItem(Q_KEY) || '[]'); } catch(e){ return []; } };
  const saveQ = (q) => localStorage.setItem(Q_KEY, JSON.stringify(q));

  async function processQueue(){
    const q = loadQ();
    if (!q.length) return;
    const rest = [];
    for (const item of q){
      try {
        const res = await fetch(item.url, { method: item.method, headers: item.headers, body: item.body });
        if (!res.ok) throw new Error('HTTP ' + res.status);
      } catch(e){ rest.push(item); }
    }
    saveQ(rest);
  }

  async function smartFetch(url, opts={}){
    const method = (opts.method || 'GET').toUpperCase();
    const isWrite = ['POST','PUT','PATCH','DELETE'].includes(method);
    if (!isWrite) return fetch(url, opts);
    if (navigator.onLine){
      try { return await fetch(url, opts); }
      catch(e){ /* fallthrough to queue */ }
    }
    const headers = opts.headers || {};
    const body = opts.body || null;
    const q = loadQ();
    q.push({ url, method, headers, body });
    saveQ(q);
    return new Response(JSON.stringify({ queued: true }), { status: 202, headers: { 'Content-Type': 'application/json' } });
  }

  window.ucsQueue = { fetch: smartFetch, processQueue };
  window.addEventListener('online', processQueue);
  document.addEventListener('DOMContentLoaded', processQueue);
})();
