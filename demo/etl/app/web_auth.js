// Inicio de sesión con Keycloak (OpenID Connect, flujo Authorization Code + PKCE).
// El usuario escribe su contraseña SOLO en la pantalla de Keycloak, nunca en esta página.
const KC = { url: 'http://localhost:8080', realm: 'retailnova', client: 'retailnova-web' };
const KC_BASE = `${KC.url}/realms/${KC.realm}/protocol/openid-connect`;
const b64u = b => btoa(String.fromCharCode(...new Uint8Array(b))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
const rnd = n => b64u(crypto.getRandomValues(new Uint8Array(n)));
const here = () => location.origin + location.pathname;

const Auth = {
  async login() {
    const verifier = rnd(32), state = rnd(16);
    sessionStorage.setItem('kc_verifier', verifier); sessionStorage.setItem('kc_state', state);
    const challenge = b64u(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier)));
    location = `${KC_BASE}/auth?` + new URLSearchParams({ client_id: KC.client, response_type: 'code', scope: 'openid',
      redirect_uri: here(), code_challenge: challenge, code_challenge_method: 'S256', state });
  },
  async handleCallback() {
    const p = new URLSearchParams(location.search);
    if (!p.get('code')) return;
    history.replaceState({}, '', location.pathname);
    if (p.get('state') !== sessionStorage.getItem('kc_state')) return;  // protección CSRF
    const r = await fetch(`${KC_BASE}/token`, { method: 'POST', headers: { 'content-type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ grant_type: 'authorization_code', client_id: KC.client, code: p.get('code'),
        redirect_uri: here(), code_verifier: sessionStorage.getItem('kc_verifier') }) });
    if (!r.ok) return;
    const j = await r.json();
    sessionStorage.setItem('kc_token', j.access_token); sessionStorage.setItem('kc_id', j.id_token || '');
    sessionStorage.setItem('kc_exp', String(Date.now() + j.expires_in * 1000));
  },
  token() {
    const t = sessionStorage.getItem('kc_token');
    return t && Date.now() < +sessionStorage.getItem('kc_exp') ? t : null;
  },
  claims() {
    const t = this.token(); if (!t) return null;
    return JSON.parse(decodeURIComponent(escape(atob(t.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')))));
  },
  roles() {
    const known = ['admin', 'gerente', 'cajero', 'atencion_cliente'];
    return ((this.claims() || {}).realm_access?.roles || []).filter(r => known.includes(r));
  },
  logout() {
    const id = sessionStorage.getItem('kc_id');
    ['kc_token', 'kc_id', 'kc_exp', 'kc_verifier', 'kc_state'].forEach(k => sessionStorage.removeItem(k));
    location = `${KC_BASE}/logout?` + new URLSearchParams({ client_id: KC.client, post_logout_redirect_uri: here(), ...(id ? { id_token_hint: id } : {}) });
  },
  // fetch con el token; devuelve {ok, status, data}
  async api(url, opts = {}) {
    const headers = { ...(opts.headers || {}) };
    const t = this.token(); if (t) headers.Authorization = 'Bearer ' + t;
    const r = await fetch(url, { ...opts, headers });
    let data = null; try { data = await r.json(); } catch (e) {}
    return { ok: r.ok, status: r.status, data };
  },
  // pinta la barra de sesión en el elemento indicado
  bar(elId) {
    const el = document.getElementById(elId), c = this.claims();
    el.innerHTML = c
      ? `👤 <b>${c.preferred_username}</b> · rol: ${this.roles().join(', ') || 'sin rol'} <button onclick="Auth.logout()">Cerrar sesión</button>`
      : `<button onclick="Auth.login()">Iniciar sesión</button>`;
  },
};
