// RetailNova · utilidades compartidas: navegación entre sistemas, formatos y estados.
const RN = {
  stores: { 'LIM-01': 'Miraflores', 'LIM-02': 'San Miguel', 'LIM-03': 'Los Olivos' },
  cat: { Laptops: '💻', Smartphones: '📱', Televisores: '📺', Audio: '🎧', Tablets: '📲', Wearables: '⌚', Monitores: '🖥️', Accesorios: '🔌' },
  erpName: 'ERP',
  apps: [
    { port: '8003', name: 'Tienda online', icon: '🛒' },
    { port: '8004', name: 'Caja de tienda', icon: '🧾' },
    { port: '8001', name: 'CRM', icon: '👥' },
    { port: '8002', name: 'ERP', icon: '🏭', erp: true },
    { port: '8005', name: 'Analytics', icon: '📊' },
  ],
  logo: `<svg viewBox="0 0 40 40" aria-hidden="true"><rect width="40" height="40" rx="10" fill="#ff7a1a"/>
    <path d="M12 30V10h8.5a6 6 0 0 1 0 12H12m8.5 0 7 8" stroke="#fff" stroke-width="3.4" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
    <circle cx="30.5" cy="10.5" r="2.6" fill="#fff"/></svg>`,
  esc: s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])),
  sol: v => 'S/ ' + Number(v || 0).toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
  num: v => Number(v || 0).toLocaleString('es-PE'),
  conIgv: p => Math.round(Number(p) * 118) / 100,
  store: id => RN.stores[id] ? `${RN.stores[id]}` : (id || '—'),
  label: { PENDIENTE: 'Pendiente', ENVIADO: 'Enviado al ERP', CONFIRMADO: 'Confirmado', RECHAZADO: 'Rechazado',
           EN_COLA: 'En cola (sin red)', FACTURADO: 'Facturado', PERMITIDO: 'Permitido', DENEGADO: 'Denegado',
           OK: 'Disponible', BAJO: 'Stock bajo', AGOTADO: 'Agotado' },
  chip(st) { return `<span class="chip st-${RN.esc(st)}">${RN.esc(RN.label[st] || st)}</span>`; },
  channel(c) { const n = { ecommerce: '🛒 Online', pos: '🏬 Tienda', api: '⚙️ API' }[c] || c; return `<span class="chip ch-${RN.esc(c)}">${n}</span>`; },
  stockState(s) { return s <= 0 ? 'AGOTADO' : s <= 5 ? 'BAJO' : 'OK'; },
  nav() {
    const el = document.getElementById('rn-nav'); if (!el) return;
    const here = location.port;
    el.className = 'rn-nav';
    el.innerHTML = `<div class="wrap"><span class="rn-brand">${RN.logo} RetailNova</span>` +
      RN.apps.map(a => `<a href="http://localhost:${a.port}/" class="${a.port === here ? 'on' : ''}">${a.icon} ${a.erp ? RN.esc(RN.erpName) + ' · ERP' : a.name}</a>`).join('') +
      `<span class="tag">Demo académica · datos sintéticos</span></div>`;
    // el nombre comercial del ERP se configura en un solo lugar (variable ERP_BRAND del ERP)
    fetch('http://localhost:8002/brand').then(r => r.json()).then(b => { RN.erpName = b.name; RN.nav(); }).catch(() => {});
  },
  sessionBox(elId) {
    const el = document.getElementById(elId); if (!el || typeof Auth === 'undefined') return;
    const c = Auth.claims();
    el.innerHTML = c
      ? `<div class="session"><div class="avatar">${RN.esc((c.given_name || c.preferred_username || '?')[0].toUpperCase())}</div>
         <div><b>${RN.esc(c.name || c.preferred_username)}</b><div class="small" style="opacity:.8">${RN.esc(Auth.roles().join(', ') || 'sin rol')}</div></div>
         <button class="btn light" onclick="Auth.logout()">Salir</button></div>`
      : `<button class="btn accent" onclick="Auth.login()">Iniciar sesión</button>`;
  },
  gate(elId, r, who) {
    const el = document.getElementById(elId);
    el.innerHTML = r.ok ? '' : r.status === 401
      ? `<div class="notice info">🔐 Inicia sesión ${who ? 'como ' + who + ' ' : ''}para continuar.</div>`
      : `<div class="notice deny">⛔ ${RN.esc(r.data?.detail || 'No tienes permiso')}</div>`;
    return r.ok;
  },
};
document.addEventListener('DOMContentLoaded', () => RN.nav());
