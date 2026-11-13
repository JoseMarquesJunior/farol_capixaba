"use strict";
/* ============================================================================
   Motor dos grafos: desenha nós e ligações num <canvas>, com zoom, arraste,
   pinça no celular, teclado e seleção. Sem biblioteca externa — a página fica
   inteira offline. A disposição (x, y) vem pronta do ETL (`etl/grafos.py`):
   o motor não calcula forças, só desenha, então a mesma rede sai sempre igual.

   A figura NÃO sequestra a rolagem da página (auditoria de UX de 26/10/2026):
   a roda do mouse só aproxima com Ctrl/⌘ ou depois de um clique na figura, e
   no toque um dedo rola a página — mover e aproximar é com dois dedos.

   Coordenadas: as do ETL, em "unidades do mapa" (o ES tem ~1.000 de altura).
   A malha do IBGE chega em lon/lat e é projetada com a MESMA fórmula do ETL.

   Nó:      { id, x, y, r, forma: "q"|"c"|"anel", cor, borda?, rotulo, prio, letraNo?, marca? }
   Ligação: { a, b (índices dos nós), w (px), cor, alfa, traco?, corRealce? }
   Fundo:   { poligonos: [{ aneis: [[x,y,…]], cor, alfa }], linhas: [[x1,y1,x2,y2]] }
   ========================================================================== */

function projetarLonLat(lon, lat) {
  const p = META.projecao;
  return [(lon - p.lon0) * Math.cos(p.lat0 * Math.PI / 180) * p.k, -(lat - p.lat0) * p.k];
}

/** Malha do IBGE projetada uma vez: cod → lista de anéis [x0,y0,x1,y1,…]. */
const MALHA = (() => {
  const saida = new Map();
  for (const f of DADOS.malha.features) {
    const g = f.geometry, polis = g.type === "Polygon" ? [g.coordinates] : g.coordinates;
    const aneis = [];
    for (const p of polis) for (const anel of p) {
      const a = new Float32Array(anel.length * 2);
      anel.forEach((c, i) => { const [x, y] = projetarLonLat(c[0], c[1]); a[2 * i] = x; a[2 * i + 1] = y; });
      aneis.push(a);
    }
    saida.set(f.properties.cod, aneis);
  }
  return saida;
})();
function fronteirasProjetadas(tipo) {
  return (DADOS.fronteiras[tipo] || []).map(s => [...projetarLonLat(s[0], s[1]), ...projetarLonLat(s[2], s[3])]);
}

function coresGrafo() {
  const cs = getComputedStyle(document.documentElement);
  const v = n => cs.getPropertyValue(n).trim();
  return { surface: v("--surface"), page: v("--page"), ink: v("--ink"), ink2: v("--ink-2"), grid: v("--grid"),
    neutro: v("--neutral-mark"), marinho: v("--tc-marinho"), municipio: v("--rd-municipio"), destaque: v("--rd-destaque"), fonte: v("--tc-fonte"),
    alcance: [v("--rd-alc1"), v("--rd-alc2"), v("--rd-alc3")], bordaAlc1: v("--rd-alc1-borda"), com: [v("--s1"), v("--s2"), v("--s3")],
    comOutra: v("--rd-com-outra"), mapa: v("--rd-mapa"), mapaBorda: v("--rd-mapa-borda"), sinal: v("--st-sinal-barra"),
    exec: v("--s1") };
}
const MOVIMENTO_REDUZIDO = matchMedia("(prefers-reduced-motion: reduce)");

class Grafo {
  constructor(caixa, opcoes) {
    this.o = opcoes || {};
    this.caixa = caixa;
    this.canvas = h("canvas", { role: "img", tabindex: "0", "aria-label": this.o.descricao || "Grafo",
      "aria-describedby": this.o.idAjuda || null });
    this.zoomBotoes = h("div", { class: "rede-zoom" },
      h("button", { type: "button", title: "Aproximar", "aria-label": "Aproximar", onclick: () => this.zoomCentro(1.6, true) }, "+"),
      h("button", { type: "button", title: "Afastar", "aria-label": "Afastar", onclick: () => this.zoomCentro(1 / 1.6, true) }, "−"),
      h("button", { type: "button", title: "Enquadrar a rede inteira", "aria-label": "Enquadrar a rede inteira", onclick: () => this.enquadrar(true, null, true) }, "⤢"));
    this.dicaEl = h("div", { class: "rede-dica", "aria-hidden": "true" });
    this.avisoEl = h("div", { class: "rede-aviso", hidden: true });
    caixa.append(this.canvas, this.zoomBotoes, this.dicaEl, this.avisoEl);
    this.ctx = this.canvas.getContext("2d");
    this.nos = []; this.arestas = []; this.fundo = null;
    this.t = { k: 1, x: 0, y: 0 }; this.kBase = 1;
    this.sel = null; this.vizinhos = new Set(); this.incidentes = new Set();
    this.passando = null; this.ativo = false; this.soSelecao = !!this.o.soSelecao;
    this.cor = coresGrafo();
    this._agendado = false;
    this._ponteiros = new Map();
    this._ligar();
    this._ro = new ResizeObserver(() => { const ant = this.largura; this._medir(); if (ant && this.largura) this._reajustar(ant); this.desenhar(); });
    this._ro.observe(caixa);
    this._medir();
  }

  /* ------------------------------------------------------------ dados */
  definir({ nos, arestas, fundo }, manterVista) {
    this.nos = nos; this.arestas = arestas; this.fundo = fundo || null;
    this.indice = new Map(nos.map((n, i) => [n.id, i]));
    this.adj = nos.map(() => []);
    arestas.forEach((e, i) => { this.adj[e.a].push(i); this.adj[e.b].push(i); });
    if (this.sel !== null && !this.indice.has(this.sel)) this.sel = null;
    this._calcularVizinhos();
    if (!manterVista) this.enquadrar(false);
    this.desenhar();
  }
  selecionar(id, centralizar) {
    this.sel = id !== null && id !== undefined && this.indice.has(id) ? id : null;
    this._calcularVizinhos();
    if (centralizar && this.sel !== null) this.focar(this.sel);
    this.desenhar();
  }
  mostrarLigacoes(soSelecao) { this.soSelecao = soSelecao; this.desenhar(); }
  descrever(texto) { this.canvas.setAttribute("aria-label", texto); }
  /** Mensagem sobre a figura (estado vazio). `conteudo` = nó ou null para esconder. */
  aviso(conteudo) { limpar(this.avisoEl); this.avisoEl.hidden = !conteudo; if (conteudo) this.avisoEl.append(conteudo); }
  /** Vista atual, para a página reabrir no mesmo enquadramento depois de um filtro. */
  vista() { return { t: { ...this.t }, kBase: this.kBase, largura: this.largura }; }
  restaurar(v) {
    if (!v || !v.largura) return;
    const f = this.largura / v.largura;
    this.t = { k: v.t.k * f, x: v.t.x * f, y: v.t.y * f }; this.kBase = v.kBase * f;
    this.desenhar();
  }
  _calcularVizinhos() {
    this.vizinhos = new Set(); this.incidentes = new Set();
    if (this.sel === null) return;
    const i = this.indice.get(this.sel);
    for (const e of this.adj[i]) { this.incidentes.add(e); const a = this.arestas[e]; this.vizinhos.add(a.a === i ? a.b : a.a); }
  }

  /* ------------------------------------------------------------ vista */
  _medir() {
    const r = this.caixa.getBoundingClientRect();
    this.largura = Math.max(1, Math.round(r.width)); this.altura = Math.max(1, Math.round(r.height));
    const dpr = window.devicePixelRatio || 1;
    this.dpr = dpr;
    this.canvas.width = Math.round(this.largura * dpr); this.canvas.height = Math.round(this.altura * dpr);
  }
  _reajustar(larguraAnterior) {
    const f = this.largura / larguraAnterior;
    if (!isFinite(f) || f <= 0) return;
    this.t = { k: this.t.k * f, x: this.t.x * f, y: this.t.y * f }; this.kBase *= f;
  }
  _caixaDe(lista) {
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (const n of lista) { x0 = Math.min(x0, n.x - n.r); y0 = Math.min(y0, n.y - n.r); x1 = Math.max(x1, n.x + n.r); y1 = Math.max(y1, n.y + n.r); }
    return isFinite(x0) ? [x0, y0, x1, y1] : [-500, -500, 500, 500];
  }
  enquadrar(desenhar = true, lista, animar) {
    const [x0, y0, x1, y1] = this._caixaDe(lista || this.nos);
    const pad = 34, w = Math.max(x1 - x0, 1), hh = Math.max(y1 - y0, 1);
    const k = Math.min((this.largura - 2 * pad) / w, (this.altura - 2 * pad) / hh);
    if (!lista) this.kBase = k;
    const kk = lista ? Math.min(k, this.kBase * 12) : k;
    const alvo = { k: kk, x: this.largura / 2 - kk * (x0 + x1) / 2, y: this.altura / 2 - kk * (y0 + y1) / 2 };
    if (animar) this._animarPara(alvo); else { this.t = alvo; if (desenhar) this.desenhar(); }
  }
  focar(id) {
    const i = this.indice.get(id);
    if (i === undefined) return;
    const grupo = [this.nos[i], ...[...this.vizinhos].map(j => this.nos[j])];
    if (grupo.length > 1) this.enquadrar(true, grupo, true);
    else { const n = this.nos[i]; const k = Math.max(this.t.k, this.kBase * 3); this._animarPara({ k, x: this.largura / 2 - k * n.x, y: this.altura / 2 - k * n.y }); }
  }
  /** Transição curta até a nova vista — o leitor não perde de onde veio. Sem animação se o sistema pede movimento reduzido. */
  _animarPara(alvo) {
    cancelAnimationFrame(this._anim || 0);
    if (MOVIMENTO_REDUZIDO.matches) { this.t = alvo; this.desenhar(); return; }
    const de = { ...this.t }, t0 = performance.now(), dur = 300;
    const passo = agora => {
      const u = Math.min(1, (agora - t0) / dur), e = 1 - Math.pow(1 - u, 3);
      const k = de.k * Math.pow(alvo.k / de.k, e);
      // interpola o ponto do mapa no centro da tela, para o zoom não "escorregar" de lado
      const cx = this.largura / 2, cy = this.altura / 2;
      const m0 = [(cx - de.x) / de.k, (cy - de.y) / de.k], m1 = [(cx - alvo.x) / alvo.k, (cy - alvo.y) / alvo.k];
      const mx = m0[0] + (m1[0] - m0[0]) * e, my = m0[1] + (m1[1] - m0[1]) * e;
      this.t = { k, x: cx - mx * k, y: cy - my * k };
      this._pintar();
      if (u < 1) this._anim = requestAnimationFrame(passo);
    };
    this._anim = requestAnimationFrame(passo);
  }
  zoomEm(px, py, fator) {
    const k = Math.max(this.kBase * 0.5, Math.min(this.kBase * 60, this.t.k * fator));
    const f = k / this.t.k;
    this.t = { k, x: px - (px - this.t.x) * f, y: py - (py - this.t.y) * f };
    this.desenhar();
  }
  zoomCentro(fator, animar) {
    const px = this.largura / 2, py = this.altura / 2;
    const k = Math.max(this.kBase * 0.5, Math.min(this.kBase * 60, this.t.k * fator)), f = k / this.t.k;
    const alvo = { k, x: px - (px - this.t.x) * f, y: py - (py - this.t.y) * f };
    if (animar) this._animarPara(alvo); else { this.t = alvo; this.desenhar(); }
  }
  raioTela(n) { return Math.max(n.forma === "q" ? 3.2 : 1.8, n.r * Math.sqrt(this.t.k * this.kBase)); }
  dica(texto, ms = 1800) {
    this.dicaEl.textContent = texto;
    this.dicaEl.classList.add("visivel");
    clearTimeout(this._tDica);
    this._tDica = setTimeout(() => this.dicaEl.classList.remove("visivel"), ms);
  }

  /* ------------------------------------------------------------ eventos */
  _ponto(evt) { const r = this.canvas.getBoundingClientRect(); return [evt.clientX - r.left, evt.clientY - r.top]; }
  _noEm(px, py) {
    let melhor = null, dist = Infinity;
    const { k, x, y } = this.t;
    for (let i = 0; i < this.nos.length; i++) {
      const n = this.nos[i];
      if (n.oculto) continue;
      const dx = n.x * k + x - px, dy = n.y * k + y - py;
      const d = Math.hypot(dx, dy), alcance = Math.max(this.raioTela(n) + 3, 10);
      if (d <= alcance && d - this.raioTela(n) < dist) { dist = d - this.raioTela(n); melhor = i; }
    }
    return melhor;
  }
  _ligar() {
    const c = this.canvas;
    c.addEventListener("wheel", e => {
      // Rolar a página por cima da figura continua rolando a página.
      if (!(e.ctrlKey || e.metaKey || this.ativo)) { this.dica("Para aproximar: Ctrl + roda do mouse — ou clique na figura e role."); return; }
      e.preventDefault();
      const [px, py] = this._ponto(e);
      this.zoomEm(px, py, Math.exp(-e.deltaY * (e.deltaMode ? 0.05 : 0.0016)));
    }, { passive: false });
    c.addEventListener("pointerdown", e => {
      this._ponteiros.set(e.pointerId, { p: this._ponto(e), tipo: e.pointerType });
      if (e.pointerType !== "touch") { this.ativo = true; c.setPointerCapture(e.pointerId); }
      this._arraste = { inicio: this._ponto(e), t: { ...this.t }, moveu: false, toque: e.pointerType === "touch" };
      if (this._ponteiros.size === 2) {
        const [a, b] = [...this._ponteiros.values()].map(v => v.p);
        const centro = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
        this._pinca = { d: Math.hypot(a[0] - b[0], a[1] - b[1]) || 1, t: { ...this.t }, centro,
          mapa: [(centro[0] - this.t.x) / this.t.k, (centro[1] - this.t.y) / this.t.k] };
        this._arraste = null;
      }
    });
    c.addEventListener("pointermove", e => {
      const p = this._ponto(e);
      if (this._ponteiros.has(e.pointerId)) this._ponteiros.get(e.pointerId).p = p;
      if (this._pinca && this._ponteiros.size === 2) {
        // Dois dedos: aproxima pela distância e move pelo ponto médio.
        e.preventDefault();
        const [a, b] = [...this._ponteiros.values()].map(v => v.p);
        const d = Math.hypot(a[0] - b[0], a[1] - b[1]), centro = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
        const k = Math.max(this.kBase * 0.5, Math.min(this.kBase * 60, this._pinca.t.k * d / this._pinca.d));
        this.t = { k, x: centro[0] - this._pinca.mapa[0] * k, y: centro[1] - this._pinca.mapa[1] * k };
        this.desenhar();
        return;
      }
      if (this._arraste && this._ponteiros.size === 1) {
        const dx = p[0] - this._arraste.inicio[0], dy = p[1] - this._arraste.inicio[1];
        if (Math.hypot(dx, dy) > 6) this._arraste.moveu = true;
        if (this._arraste.moveu && this._arraste.toque) { if (!this._avisouToque) { this._avisouToque = true; this.dica("Use dois dedos para mover e aproximar a figura.", 2600); } return; }
        if (this._arraste.moveu) {
          this.t = { k: this._arraste.t.k, x: this._arraste.t.x + dx, y: this._arraste.t.y + dy };
          c.classList.add("arrastando"); esconderDica(); this.desenhar(); return;
        }
      }
      if (e.pointerType === "touch") return;
      const i = this._noEm(p[0], p[1]);
      const n = i === null ? null : this.nos[i];
      c.classList.toggle("sobre-no", !!n);
      if (n !== this.passando) { this.passando = n; this.desenhar(); }
      if (n && this.o.aoPassar) mostrarDica(e, this.o.aoPassar(n)); else esconderDica();
    });
    const soltar = e => {
      const arr = this._arraste;
      this._ponteiros.delete(e.pointerId);
      if (this._ponteiros.size < 2) this._pinca = null;
      c.classList.remove("arrastando");
      if (arr && !arr.moveu && e.type === "pointerup" && this._ponteiros.size === 0) {
        const [px, py] = this._ponto(e);
        const i = this._noEm(px, py);
        if (this.o.aoClicar) this.o.aoClicar(i === null ? null : this.nos[i]);
      }
      if (this._ponteiros.size === 0) this._arraste = null;
    };
    c.addEventListener("pointerup", soltar);
    c.addEventListener("pointercancel", soltar);
    c.addEventListener("pointerleave", e => {
      if (e.pointerType !== "touch") this.ativo = false;
      if (this.passando) { this.passando = null; this.desenhar(); }
      esconderDica();
    });
    c.addEventListener("dblclick", e => { const [px, py] = this._ponto(e); this.zoomEm(px, py, 2); });
    c.addEventListener("keydown", e => {
      const passo = 60;
      const acoes = { "+": () => this.zoomCentro(1.4, true), "=": () => this.zoomCentro(1.4, true), "-": () => this.zoomCentro(1 / 1.4, true),
        ArrowLeft: () => this._mover(passo, 0), ArrowRight: () => this._mover(-passo, 0), ArrowUp: () => this._mover(0, passo),
        ArrowDown: () => this._mover(0, -passo), "0": () => this.enquadrar(true, null, true), Escape: () => this.o.aoClicar && this.o.aoClicar(null) };
      if (acoes[e.key]) { e.preventDefault(); acoes[e.key](); }
    });
    matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => { this.cor = coresGrafo(); this.desenhar(); });
  }
  _mover(dx, dy) { this.t = { ...this.t, x: this.t.x + dx, y: this.t.y + dy }; this.desenhar(); }

  /* ------------------------------------------------------------ desenho */
  desenhar() {
    if (this._agendado) return;
    this._agendado = true;
    requestAnimationFrame(() => { this._agendado = false; this._pintar(); });
  }
  _pintar() {
    if (!this.caixa.isConnected) return;
    const { ctx, dpr } = this, c = this.cor, { k, x, y } = this.t;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = c.surface; ctx.fillRect(0, 0, this.largura, this.altura);
    const foco = this.sel !== null;
    if (this.fundo) {
      ctx.setTransform(dpr * k, 0, 0, dpr * k, dpr * x, dpr * y);
      for (const p of this.fundo.poligonos || []) {
        ctx.beginPath();
        for (const a of p.aneis) { ctx.moveTo(a[0], a[1]); for (let i = 2; i < a.length; i += 2) ctx.lineTo(a[i], a[i + 1]); ctx.closePath(); }
        ctx.globalAlpha = p.alfa ?? 1; ctx.fillStyle = p.cor || c.mapa; ctx.fill("evenodd");
        ctx.globalAlpha = 1; ctx.lineWidth = 0.8 / k; ctx.strokeStyle = c.mapaBorda; ctx.stroke();
      }
      if (this.fundo.linhas && this.fundo.linhas.length) {
        ctx.beginPath();
        for (const s of this.fundo.linhas) { ctx.moveTo(s[0], s[1]); ctx.lineTo(s[2], s[3]); }
        ctx.lineWidth = 2.2 / k; ctx.strokeStyle = c.ink; ctx.lineJoin = "round"; ctx.globalAlpha = 0.85; ctx.stroke(); ctx.globalAlpha = 1;
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    const grupos = new Map();
    const realce = [];
    const esconderResto = this.soSelecao;
    this.arestas.forEach((e, i) => {
      const na = this.nos[e.a], nb = this.nos[e.b];
      if (na.oculto || nb.oculto) return;
      if (foco && this.incidentes.has(i)) { realce.push(e); return; }
      if (esconderResto) return;
      const alfa = foco ? Math.min(0.05, e.alfa ?? 0.3) : (e.alfa ?? 0.3);
      const chave = (e.cor || c.neutro) + "|" + alfa + "|" + Math.round(e.w * 2) / 2 + "|" + (e.traco ? e.traco.join(",") : "");
      if (!grupos.has(chave)) grupos.set(chave, []);
      grupos.get(chave).push(e);
    });
    const tracar = (lista, cor, alfa, w, traco) => {
      ctx.beginPath();
      for (const e of lista) { const a = this.nos[e.a], b = this.nos[e.b]; ctx.moveTo(a.x * k + x, a.y * k + y); ctx.lineTo(b.x * k + x, b.y * k + y); }
      ctx.globalAlpha = alfa; ctx.strokeStyle = cor; ctx.lineWidth = w; ctx.setLineDash(traco || []); ctx.stroke();
    };
    for (const [chave, lista] of grupos) {
      const [cor, alfa, w, traco] = chave.split("|");
      tracar(lista, cor, +alfa, +w, traco ? traco.split(",").map(Number) : null);
    }
    for (const e of realce) tracar([e], e.corRealce || c.destaque, 0.9, Math.max(1.4, e.w * 1.3), e.traco);
    ctx.setLineDash([]); ctx.globalAlpha = 1;
    const ordem = [];
    this.nos.forEach((n, i) => { if (!n.oculto) ordem.push(i); });
    const iSel = foco ? this.indice.get(this.sel) : -1;
    const importante = i => !foco || i === iSel || this.vizinhos.has(i);
    ordem.sort((a, b) => (importante(a) - importante(b)) || (this.nos[a].forma === "q") - (this.nos[b].forma === "q") || this.nos[b].r - this.nos[a].r);
    for (const i of ordem) {
      const n = this.nos[i], rs = this.raioTela(n), px = n.x * k + x, py = n.y * k + y;
      if (px < -rs - 40 || py < -rs - 40 || px > this.largura + rs + 40 || py > this.altura + rs + 40) continue;
      ctx.globalAlpha = importante(i) ? 1 : 0.18;
      ctx.beginPath();
      if (n.forma === "q") ctx.rect(px - rs, py - rs, 2 * rs, 2 * rs);
      else ctx.arc(px, py, rs, 0, 2 * Math.PI);
      if (n.forma === "anel") { ctx.fillStyle = c.surface; ctx.fill(); ctx.lineWidth = Math.max(1.5, rs * 0.45); ctx.strokeStyle = n.cor; ctx.stroke(); }
      else {
        ctx.fillStyle = n.cor; ctx.fill();
        // Contorno: o anel da cor da superfície separa nós que se tocam; o nó claro ganha
        // contorno escuro, para o desenho passar de 3:1 contra o fundo (WCAG 1.4.11).
        ctx.lineWidth = 1.2; ctx.strokeStyle = n.borda || c.surface; ctx.stroke();
      }
      if (n.marca) { ctx.beginPath(); ctx.arc(px, py, rs + 3, 0, 2 * Math.PI); ctx.lineWidth = 2.2; ctx.strokeStyle = n.marca; ctx.stroke(); }
      const sel = this.sel === n.id, passando = this.passando === n;
      if (sel || passando) {
        ctx.globalAlpha = 1; ctx.beginPath();
        if (n.forma === "q") ctx.rect(px - rs - 3, py - rs - 3, 2 * rs + 6, 2 * rs + 6); else ctx.arc(px, py, rs + 3.5, 0, 2 * Math.PI);
        ctx.lineWidth = sel ? 3 : 2; ctx.strokeStyle = c.ink; ctx.stroke();
      }
    }
    ctx.globalAlpha = 1;
    this._rotulos(ordem, importante, iSel);
  }
  _rotulos(ordem, importante, iSel) {
    const { ctx } = this, c = this.cor, { k, x, y } = this.t;
    const ocupado = [];
    const cabe = (x0, y0, x1, y1) => !ocupado.some(o => x0 < o[2] && x1 > o[0] && y0 < o[3] && y1 > o[1]);
    const zoomRel = k / this.kBase;
    const candidatos = [];
    for (const i of ordem) {
      const n = this.nos[i];
      if (!n.rotulo) continue;
      let prio;
      if (i === iSel) prio = 1e9;
      else if (this.passando === n) prio = 1e8;
      else if (iSel >= 0) prio = this.vizinhos.has(i) ? 1e6 + n.r : (n.forma === "q" && zoomRel > 1.6 ? n.r : -1);
      else if (n.forma === "q") prio = zoomRel >= (this.o.zoomRotuloMunicipio ?? 1.25) ? 1e5 + n.r : -1;
      // Figura estreita (celular): só os maiores ganham rótulo, senão o nome cobre a rede.
      else prio = zoomRel >= 2 ? n.r * (n.prio || 1) : (n.prio > (this.largura < 600 ? 8.4 : 5) ? n.prio : -1);
      if (prio > 0) candidatos.push([prio, i]);
    }
    candidatos.sort((a, b) => b[0] - a[0]);
    ctx.font = (this.o.fonteRotulo || 12) + "px " + c.fonte;
    ctx.textBaseline = "middle"; ctx.lineJoin = "round";
    let feitos = 0;
    for (const [prio, i] of candidatos) {
      if (feitos > 160) break;
      const n = this.nos[i], rs = this.raioTela(n), px = n.x * k + x, py = n.y * k + y;
      const curto = n.rotulo.length > 34 ? n.rotulo.slice(0, 32) + "…" : n.rotulo;
      const w = ctx.measureText(curto).width, hgt = 14;
      // À direita do nó; perto da borda direita, à esquerda — o rótulo nunca sai da figura.
      let x0 = px + rs + 4;
      if (x0 + w > this.largura - 52) x0 = px - rs - 4 - w;
      x0 = Math.max(4, x0);
      const y0 = py - hgt / 2;
      if (x0 > this.largura || py < -10 || py > this.altura + 10) continue;
      if (prio < 1e8 && !cabe(x0, y0, x0 + w, y0 + hgt)) continue;
      ocupado.push([x0 - 2, y0, x0 + w + 2, y0 + hgt]);
      ctx.globalAlpha = importante(i) ? 1 : 0.5;
      ctx.lineWidth = 3.5; ctx.strokeStyle = c.surface; ctx.strokeText(curto, x0, py);
      ctx.fillStyle = n.forma === "q" ? c.marinho : c.ink; ctx.fillText(curto, x0, py);
      feitos++;
    }
    if (this.o.letras) {
      ctx.font = "700 11px " + c.fonte; ctx.textAlign = "center";
      for (const i of ordem) {
        const n = this.nos[i];
        if (!n.letraNo) continue;
        const px = n.x * k + x, py = n.y * k + y;
        ctx.globalAlpha = importante(i) ? 1 : 0.4;
        ctx.lineWidth = 3; ctx.strokeStyle = c.surface; ctx.strokeText(n.letraNo, px, py - this.raioTela(n) - 7);
        ctx.fillStyle = c.ink; ctx.fillText(n.letraNo, px, py - this.raioTela(n) - 7);
      }
      ctx.textAlign = "start";
    }
    ctx.globalAlpha = 1;
  }
}

/** Fundo do mapa com os 78 municípios (cor única ou por município). */
function fundoMapa(corDe, linhas) {
  return { poligonos: MUN.map((m, i) => ({ aneis: MALHA.get(m.cod) || [], ...(corDe ? corDe(i) : {}) })), linhas: linhas || [] };
}
