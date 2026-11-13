"""
O escritorio em 3D: um predio terreo visto em corte, a noite, no meio de um jardim.

Le /api/escritorio (esteira.quadro_do_escritorio). Cada time de streamer tem a propria sala com quatro
pessoas; qualidade, compliance, gerencia, diretoria e o CEO ficam em salas ao norte do corredor, e ha
sala de reuniao, cozinha e lounge. O que cada pessoa mostra que esta fazendo vem do diario real da
producao e da esteira (esteira.registrar_evento): nada de status inventado. Quando um corte muda de
etapa entre duas leituras, alguem leva a fita ate a mesa de quem valida em seguida. As pausas (cafe,
sinuca, visita a um colega) sao so ambiente, e o ritmo delas segue o humor do time.

O botao de expediente liga e desliga a vigia das lives (expediente.py).

O three.js vem de CDN com versao fixa, e nao copiado para o repositorio: sao ~700 KB que so esta pagina
usa, e a ferramenta ja depende de internet para tudo. Se o CDN nao carregar, a pagina cai para
/escritorio/mesas, que nao depende de nada externo.

?demo=1 troca os dados reais por uma simulacao no navegador, para ver o escritorio em movimento sem
ter a vigia rodando.
"""

PAGINA = r"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Escritório</title>
<style>
  :root {
    --fundo: #070a11; --painel: #0e131d; --painel2: #161d2b; --borda: #26303f; --texto: #f1ece0; --fraco: #9aa3b2;
    --latao: #d4af5a; --latao2: #8f7434; --alta: #3ddc84; --baixa: #ff5d5d; --ambar: #f0a63a;
    --serifa: "Playfair Display", "Bodoni MT", Didot, Georgia, "Times New Roman", serif;
  }
  * { box-sizing: border-box; }
  html, body { height: 100%; }
  body { margin: 0; background: var(--fundo); color: var(--texto); font: 14px/1.45 system-ui, "Segoe UI", sans-serif;
         overflow: hidden; display: flex; flex-direction: column; }
  header { display: flex; align-items: center; gap: 8px 22px; padding: 10px 20px; flex: none; flex-wrap: wrap;
           background: linear-gradient(#0f1522, #0a0e17); border-bottom: 1px solid var(--latao2); }
  .marca { font-family: var(--serifa); font-size: 19px; letter-spacing: .14em; text-transform: uppercase; color: var(--latao);
           margin: 0; font-weight: 700; white-space: nowrap; }
  nav { display: flex; gap: 4px; }
  nav a { color: var(--fraco); text-decoration: none; padding: 6px 12px; border-radius: 6px; font-size: 13px;
          letter-spacing: .04em; text-transform: uppercase; }
  nav a:hover { color: var(--texto); }
  nav a[aria-current] { color: var(--latao); background: #1a2231; }
  nav .conta { background: var(--baixa); color: #1a0606; border-radius: 999px; padding: 0 7px; font-weight: 700; margin-left: 6px; }
  #comodos { display: flex; gap: 2px; background: var(--painel2); border-radius: 8px; padding: 3px; }
  #comodos button { background: none; border: 0; color: var(--fraco); font: inherit; font-size: 12px; padding: 4px 10px;
                    border-radius: 6px; cursor: pointer; white-space: nowrap; }
  #comodos button:hover { color: var(--texto); }
  #comodos button[aria-pressed="true"] { background: var(--latao); color: #1a1206; font-weight: 600; }
  #demo { color: #1a1206; background: var(--ambar); border-radius: 4px; padding: 2px 8px; font-size: 11px; font-weight: 700;
          letter-spacing: .08em; text-transform: uppercase; }
  #hora { margin-left: auto; color: var(--fraco); font-variant-numeric: tabular-nums; font-size: 13px; }
  #palco { position: relative; flex: 1; min-height: 0; }
  canvas { display: block; width: 100%; height: 100%; touch-action: none; }
  #baloes { position: absolute; inset: 0; pointer-events: none; overflow: hidden; }
  .balao { position: absolute; transform: translate(-50%, -100%); background: #f6f1e4; color: #191510; border-radius: 10px;
           padding: 3px 9px; font-size: 12px; font-weight: 600; white-space: nowrap; box-shadow: 0 4px 14px #0009;
           max-width: 260px; overflow: hidden; text-overflow: ellipsis; }
  .balao.bom { background: var(--alta); } .balao.ruim { background: var(--baixa); color: #fff; }
  .painel { position: absolute; top: 12px; bottom: 76px; width: 292px; display: flex; flex-direction: column; gap: 10px;
            pointer-events: none; }
  .painel > * { pointer-events: auto; }
  #esquerda { left: 12px; } #direita { right: 12px; }
  .cartao { background: color-mix(in srgb, var(--painel) 90%, transparent); border: 1px solid var(--borda); border-radius: 12px;
            padding: 12px; backdrop-filter: blur(6px); }
  .cartao h2 { margin: 0 0 8px; font-size: 11px; letter-spacing: .1em; text-transform: uppercase; color: var(--fraco); font-weight: 600; }
  #placar { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
  #placar div { background: color-mix(in srgb, var(--painel) 90%, transparent); border: 1px solid var(--borda); border-radius: 12px;
                padding: 10px 12px; font-size: 11px; color: var(--fraco); letter-spacing: .06em; text-transform: uppercase; backdrop-filter: blur(6px); }
  #placar b { display: block; font: 700 24px/1.15 var(--serifa); color: var(--alta); font-variant-numeric: tabular-nums; letter-spacing: 0; }
  #placar div.alerta b { color: var(--baixa); }
  #expediente p { margin: 0 0 8px; font-size: 13px; }
  #expediente button { width: 100%; border: 0; border-radius: 8px; padding: 9px; font: inherit; font-weight: 700; cursor: pointer;
                       background: var(--latao); color: #1a1206; }
  #expediente button.fechar { background: none; color: var(--baixa); border: 1px solid color-mix(in srgb, var(--baixa) 60%, transparent); }
  #expediente button:disabled { opacity: .6; cursor: progress; }
  #passar { display: grid; gap: 8px; }
  #passar input, #passar select { width: 100%; background: #080b12; color: var(--texto); border: 1px solid var(--borda); border-radius: 8px;
                                  padding: 7px 9px; font: inherit; font-size: 13px; min-width: 0; }
  #passar .linha { display: grid; grid-template-columns: 1fr 64px; gap: 8px; }
  #passar button { border: 1px solid var(--latao2); border-radius: 8px; padding: 8px; font: inherit; font-weight: 700; cursor: pointer;
                   background: none; color: var(--latao); }
  #passar button:hover { background: var(--painel2); }
  #passar button:disabled { opacity: .6; cursor: progress; }
  #retorno { margin: 0; font-size: 12px; color: var(--fraco); }
  #retorno:empty { display: none; }
  #retorno.erro { color: var(--baixa); }
  #fila { list-style: none; margin: 0; padding: 0; display: grid; gap: 4px; font-size: 12px; }
  #fila li { display: grid; grid-template-columns: auto 1fr; gap: 6px; align-items: baseline; }
  #fila li span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--fraco); }
  #fila b { font-weight: 700; color: var(--latao); }
  #fila b.feito { color: var(--alta); } #fila b.erro { color: var(--baixa); }
  input:focus-visible, select:focus-visible { outline: 2px solid var(--latao); outline-offset: 1px; }
  .rolavel { flex: 1; min-height: 0; overflow-y: auto; scrollbar-width: thin; scrollbar-color: var(--borda) transparent; }
  .time { margin: 0 0 10px; }
  .time h3 { margin: 0 0 4px; font-size: 13px; display: flex; align-items: center; gap: 6px; cursor: pointer; }
  .ponto { width: 8px; height: 8px; border-radius: 50%; background: var(--latao); flex: none; }
  .ponto.animado { background: var(--alta); } .ponto.cauteloso { background: var(--ambar); } .ponto.pressao { background: var(--baixa); }
  .ponto.fora { background: var(--borda); }
  .agente { display: grid; grid-template-columns: 22px 1fr; gap: 0 8px; padding: 3px 0; font-size: 12px; }
  .agente i { grid-row: span 2; width: 22px; height: 22px; border-radius: 50%; display: grid; place-items: center; font-style: normal;
              font-weight: 700; font-size: 11px; color: #10131a; }
  .agente small { color: var(--fraco); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .agente small.ativo { color: var(--alta); }
  #feed { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; }
  #feed li { background: var(--painel2); border-radius: 8px; padding: 7px 9px; font-size: 12px; }
  #feed b { color: var(--latao); font-weight: 600; }
  #feed time { float: right; color: var(--fraco); font-variant-numeric: tabular-nums; font-size: 11px; }
  #feed span { display: block; color: var(--texto); overflow-wrap: anywhere; }
  .vazio { color: var(--fraco); font-size: 12px; margin: 0; }
  #ficha[hidden] { display: none; }
  #ficha { position: relative; border-color: var(--latao2); max-height: 62%; overflow-y: auto; flex: none; }
  #ficha h2 { margin: 0 26px 2px 0; font: 700 19px/1.2 var(--serifa); color: var(--latao); letter-spacing: 0; text-transform: none; }
  #ficha h3 { margin: 12px 0 6px; font-size: 11px; letter-spacing: .1em; text-transform: uppercase; color: var(--fraco); font-weight: 600; }
  #ficha p { margin: 0; color: var(--fraco); font-size: 13px; }
  #ficha .numeros { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; margin-top: 10px; }
  #ficha .numeros div { background: var(--painel2); border-radius: 8px; padding: 7px 4px; text-align: center; font-size: 11px; color: var(--fraco); }
  #ficha .numeros b { display: block; font: 700 20px/1.1 var(--serifa); color: var(--texto); font-variant-numeric: tabular-nums; }
  #ficha ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; }
  #ficha li { font-size: 13px; color: var(--texto); }
  #ficha li small { color: var(--fraco); display: block; }
  .humor { display: inline-block; border-radius: 999px; padding: 2px 10px; font-size: 12px; font-weight: 700; margin-top: 8px;
           background: var(--latao); color: #1a1206; }
  .humor.animado { background: var(--alta); } .humor.cauteloso { background: var(--ambar); } .humor.pressao { background: var(--baixa); color: #fff; }
  #ficha .aviso { color: var(--ambar); margin-top: 8px; }
  #ficha a { color: var(--latao); font-size: 14px; display: inline-block; margin-top: 10px; }
  #fechar { position: absolute; top: 6px; right: 6px; background: none; border: 0; color: var(--fraco); font-size: 20px;
            cursor: pointer; line-height: 1; padding: 4px 8px; }
  #esteira { position: absolute; left: 50%; bottom: 14px; transform: translateX(-50%); display: flex; align-items: center; gap: 4px;
             background: color-mix(in srgb, var(--painel) 92%, transparent); border: 1px solid var(--latao2); border-radius: 12px;
             padding: 6px; max-width: calc(100% - 24px); overflow-x: auto; backdrop-filter: blur(6px); }
  #esteira button { background: none; border: 0; color: var(--fraco); font: inherit; font-size: 12px; cursor: pointer;
                    padding: 5px 10px; border-radius: 8px; display: flex; flex-direction: column; align-items: center; white-space: nowrap; }
  #esteira button:hover { background: var(--painel2); color: var(--texto); }
  #esteira b { font: 700 19px/1.1 var(--serifa); color: var(--latao); font-variant-numeric: tabular-nums; }
  #esteira button.voce b { color: var(--alta); }
  #esteira button.voce.cheia b { color: var(--baixa); }
  #esteira i { color: var(--latao2); font-style: normal; }
  button:focus-visible, a:focus-visible { outline: 2px solid var(--latao); outline-offset: 2px; }
  @media (max-width: 1050px) { #esquerda { display: none; } #direita { width: min(292px, calc(100% - 24px)); }
                               #direita #comunicacao { display: none; } #hora, #comodos { display: none; } }
</style>
<script type="importmap">
{ "imports": {
    "three": "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js",
    "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/"
} }
</script>
</head>
<body>
<header>
  <p class="marca" id="marca">Agência de Cortes</p>
  <nav>
    <a href="/escritorio" aria-current="page">Escritório</a>
    <a href="/">Aprovação<span class="conta" id="pendentes" hidden></span></a>
    <a href="/escritorio/mesas">Lista</a>
  </nav>
  <div id="comodos" role="group" aria-label="Ir para um cômodo"></div>
  <span id="demo" hidden>Demonstração</span>
  <span id="hora"></span>
</header>
<div id="palco">
  <canvas id="cena" aria-label="Escritório em 3D: salas dos times, gestão, diretoria, cozinha e lounge"></canvas>
  <div id="baloes"></div>
  <div class="painel" id="esquerda">
    <div id="placar"></div>
    <div class="cartao" id="expediente"></div>
    <form class="cartao" id="passar">
      <h2>Passar uma live para um time</h2>
      <input type="url" id="link" placeholder="Link do canal ou da live" required aria-label="Link do canal ou da live">
      <div class="linha">
        <select id="paraTime" aria-label="Time que vai cuidar"></select>
        <input type="number" id="quantos" min="1" max="20" value="5" aria-label="Quantos cortes" title="Quantos cortes">
      </div>
      <button type="submit">Enviar para o time</button>
      <p id="retorno" role="status"></p>
      <ul id="fila"></ul>
    </form>
    <div class="cartao rolavel"><h2>Atividade dos agentes</h2><div id="agentes"></div></div>
  </div>
  <div class="painel" id="direita">
    <aside class="cartao" id="ficha" hidden></aside>
    <div class="cartao rolavel" id="comunicacao"><h2>Comunicação</h2><ul id="feed"></ul></div>
  </div>
  <div id="esteira" role="group" aria-label="Cortes em cada etapa da aprovação"></div>
</div>
<script type="module">
let THREE, OrbitControls, EffectComposer, RenderPass, UnrealBloomPass, OutputPass;
try {
  THREE = await import("three");
  ({ OrbitControls } = await import("three/addons/controls/OrbitControls.js"));
  ({ EffectComposer } = await import("three/addons/postprocessing/EffectComposer.js"));
  ({ RenderPass } = await import("three/addons/postprocessing/RenderPass.js"));
  ({ UnrealBloomPass } = await import("three/addons/postprocessing/UnrealBloomPass.js"));
  ({ OutputPass } = await import("three/addons/postprocessing/OutputPass.js"));
} catch {
  // sem o three.js (CDN fora do ar, sem internet) a versao em lista mostra os mesmos dados
  location.replace("/escritorio/mesas");
  throw new Error("three.js nao carregou");
}

const DEMO = new URLSearchParams(location.search).has("demo");
const calmo = matchMedia("(prefers-reduced-motion: reduce)").matches;
const $ = id => document.getElementById(id);
const palco = $("palco"), ficha = $("ficha"), baloes = $("baloes");
const el = (tag, props = {}, filhos = []) => {
  const n = Object.assign(document.createElement(tag), props);
  filhos.forEach(f => n.append(f));
  return n;
};
const um = lista => lista[Math.floor(Math.random() * lista.length)];
// na placa da sala, canal sem nome de cliente aparece sem o prefixo da plataforma ("kick:coringa" -> "CORINGA")
const curto = nome => nome.split(":").pop().toUpperCase();
// numero estavel a partir de um texto: a mesma pessoa tem sempre a mesma cara e a mesma roupa
function semente(txt) { let h = 2166136261; for (const c of txt) h = Math.imul(h ^ c.codePointAt(0), 16777619); return h >>> 0; }
const corDe = txt => `hsl(${semente(txt) % 360} 60% 68%)`;
const PAUSAS = ["Café?", "Já volto", "Uma partida?", "Cinco minutos", "Água"];

// ------------------------------------------------------------------ cena
const renderer = new THREE.WebGLRenderer({ canvas: $("cena"), antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
const cena = new THREE.Scene();
cena.background = new THREE.Color(0x05080d);
cena.fog = new THREE.Fog(0x05080d, 70, 190);
const camera = new THREE.PerspectiveCamera(30, 1, 1, 500);
const controles = new OrbitControls(camera, renderer.domElement);
controles.enableDamping = !calmo;
controles.maxPolarAngle = Math.PI / 2.3;  // nao deixa a camera ir para baixo do piso
controles.minDistance = 10;
const compositor = new EffectComposer(renderer);
compositor.addPass(new RenderPass(cena, camera));
// brilho leve so no que emite luz (telas, luminarias, postes): e o que separa o predio aceso do jardim escuro
compositor.addPass(new UnrealBloomPass(new THREE.Vector2(1, 1), 0.3, 0.6, 0.9));
compositor.addPass(new OutputPass());

cena.add(new THREE.HemisphereLight(0xfff1dd, 0x2c2218, 1.7));
const teto = new THREE.DirectionalLight(0xffe6c4, 2.6);  // faz o papel da iluminacao do teto, que o corte removeu
teto.castShadow = true;
teto.shadow.mapSize.set(2048, 2048);
teto.shadow.bias = -0.0005;
cena.add(teto, teto.target);

function tela(largura, altura, desenhar, repetir = false) {
  const c = el("canvas", { width: largura, height: altura });
  desenhar(c.getContext("2d"), largura, altura);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  if (repetir) t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.anisotropy = 4;
  return t;
}
function granulado(g, l, a, cores, quantos) {
  for (let i = 0; i < quantos; i++) { g.fillStyle = um(cores); g.fillRect(Math.random() * l, Math.random() * a, 2, 2); }
}
// pisos: cada tipo de sala tem o seu, como numa planta decorada
const PISOS = {
  madeira: tela(128, 128, (g, l) => {  // espinha de peixe
    const tons = ["#a37246", "#94663b", "#ad7d4f", "#9b6b40"];
    g.fillStyle = "#7a5330"; g.fillRect(0, 0, l, l);
    for (let col = -1; col < 5; col++) for (let lin = -1; lin < 9; lin++) {
      g.save(); g.translate(col * 32 + 16, lin * 16 + (col % 2 ? 8 : 0)); g.rotate(col % 2 ? Math.PI / 4 : -Math.PI / 4);
      g.fillStyle = um(tons); g.fillRect(-21, -5, 42, 10); g.restore();
    }
  }, true),
  carpete: tela(64, 64, (g, l, a) => { g.fillStyle = "#7c2a27"; g.fillRect(0, 0, l, a); granulado(g, l, a, ["#8a332f", "#6d2320", "#913a35"], 500); }, true),
  azul: tela(64, 64, (g, l, a) => { g.fillStyle = "#2b3a52"; g.fillRect(0, 0, l, a); granulado(g, l, a, ["#33445f", "#243147"], 500); }, true),
  frio: tela(64, 64, (g, l, a) => { g.fillStyle = "#e6e2da"; g.fillRect(0, 0, l, a); g.fillStyle = "#bdb8ae"; g.fillRect(0, 0, 32, 32); g.fillRect(32, 32, 32, 32); }, true),
  grama: tela(128, 128, (g, l, a) => { g.fillStyle = "#16301c"; g.fillRect(0, 0, l, a); granulado(g, l, a, ["#1b3a22", "#122818", "#20442a"], 1800); }, true),
  calcada: tela(64, 64, (g, l, a) => { g.fillStyle = "#6f6c66"; g.fillRect(0, 0, l, a); g.strokeStyle = "#55524d"; g.lineWidth = 2; g.strokeRect(1, 1, 30, 30); g.strokeRect(33, 1, 30, 30); g.strokeRect(-15, 33, 30, 30); g.strokeRect(17, 33, 30, 30); g.strokeRect(49, 33, 30, 30); }, true),
};
const mat = (cor, extra = {}) => new THREE.MeshStandardMaterial({ color: cor, roughness: 0.8, ...extra });
const MAT = {
  parede: mat(0xece6da, { roughness: 0.9 }), rodape: mat(0x34363d), tampo: mat(0xd8b88a, { roughness: 0.5 }), branco: mat(0xf2efe8),
  escuro: mat(0x17191e, { roughness: 0.6 }), cinza: mat(0x4a4f58), cromo: mat(0x9aa3ad, { metalness: 0.9, roughness: 0.3 }),
  sofa: mat(0x9a2f2a, { roughness: 0.7 }), feltro: mat(0x1f7a4d, { roughness: 1 }), nogueira: mat(0x5a3a22, { roughness: 0.5 }),
  fita: mat(0xf2c230, { roughness: 0.4, emissive: 0x6b4a00, emissiveIntensity: 0.5 }),
  luz: mat(0xfff0c8, { emissive: 0xffd58a, emissiveIntensity: 2.2 }), planta: mat(0x2f6b3a), vaso: mat(0xcfc7b8),
  pinheiro: mat(0x163a22, { roughness: 1 }), tronco: mat(0x3a2a1c), asfalto: mat(0x1c1e22, { roughness: 1 }),
};
function caixa(l, a, p, material, x = 0, y = 0, z = 0, sombra = true) {
  const m = new THREE.Mesh(new THREE.BoxGeometry(l, a, p), material);
  m.position.set(x, y, z); m.castShadow = sombra; m.receiveShadow = true;
  return m;
}
function cilindro(r1, r2, a, material, x = 0, y = 0, z = 0, lados = 14) {
  const m = new THREE.Mesh(new THREE.CylinderGeometry(r1, r2, a, lados), material);
  m.position.set(x, y, z); m.castShadow = true; m.receiveShadow = true;
  return m;
}
function piso(grupo, tipo, x0, z0, x1, z1, y = 0.012) {
  const t = PISOS[tipo].clone(); t.needsUpdate = true;
  const escala = { madeira: 1.9, carpete: 1.2, azul: 1.2, frio: 1.2, grama: 6, calcada: 1.6 }[tipo];
  t.repeat.set((x1 - x0) / escala, (z1 - z0) / escala);
  const m = new THREE.Mesh(new THREE.PlaneGeometry(x1 - x0, z1 - z0), new THREE.MeshStandardMaterial({ map: t, roughness: tipo === "madeira" ? 0.45 : 0.95 }));
  m.rotation.x = -Math.PI / 2; m.position.set((x0 + x1) / 2, y, (z0 + z1) / 2); m.receiveShadow = true; grupo.add(m);
  return m;
}
const ALTURA = 1.9;
function muro(grupo, x0, z0, x1, z1) {
  // parede grossa e branca com acabamento escuro em cima, como numa maquete em corte
  const l = Math.abs(x1 - x0) + 0.2, p = Math.abs(z1 - z0) + 0.2, x = (x0 + x1) / 2, z = (z0 + z1) / 2;
  grupo.add(caixa(l, ALTURA, p, MAT.parede, x, ALTURA / 2, z), caixa(l + 0.02, 0.08, p + 0.02, MAT.rodape, x, ALTURA + 0.04, z, false));
}

function grafico(cor, tendencia) {
  return tela(128, 80, (g, l, a) => {
    g.fillStyle = "#04070c"; g.fillRect(0, 0, l, a);
    g.strokeStyle = cor; g.lineWidth = 3; g.beginPath();
    let y = a / 2 - tendencia * 18;
    for (let x = 0; x <= l; x += 8) { y += (Math.random() - 0.5 - tendencia * 0.35) * 9; y = Math.max(8, Math.min(a - 8, y)); x ? g.lineTo(x, y) : g.moveTo(x, y); }
    g.stroke(); g.fillStyle = cor; g.fillRect(6, 6, 34, 6);
  });
}
const TELAS = { animado: grafico("#3ddc84", 1), normal: grafico("#d4af5a", 0.2), cauteloso: grafico("#f0a63a", -0.3),
                pressao: grafico("#ff5d5d", -1), gestao: grafico("#6fb7ff", 0.1), desligada: tela(8, 8, g => { g.fillStyle = "#020304"; g.fillRect(0, 0, 8, 8); }) };

// ----------------------------------------------------------------- moveis
function mesa(grupo, x, z, chefe = false) {
  const g = new THREE.Group(); g.position.set(x, 0, z);
  const larg = chefe ? 2.4 : 1.7, prof = chefe ? 1.05 : 0.85;
  g.add(caixa(larg, 0.06, prof, chefe ? MAT.nogueira : MAT.tampo, 0, 0.76, 0));
  for (const lado of [-1, 1]) g.add(caixa(0.06, 0.74, prof - 0.1, chefe ? MAT.nogueira : MAT.branco, lado * (larg / 2 - 0.05), 0.37, 0));
  const telas = [];
  for (const dx of chefe ? [-0.36, 0.36] : [0]) {
    g.add(caixa(0.22, 0.03, 0.16, MAT.escuro, dx, 0.8, -0.2, false), caixa(0.05, 0.16, 0.05, MAT.escuro, dx, 0.88, -0.2, false));
    g.add(caixa(0.66, 0.42, 0.04, MAT.escuro, dx, 1.14, -0.2));
    const t = new THREE.Mesh(new THREE.PlaneGeometry(0.6, 0.36), new THREE.MeshBasicMaterial({ map: TELAS.desligada, toneMapped: false }));
    t.position.set(dx, 1.14, -0.178); g.add(t); telas.push(t);
  }
  g.add(caixa(0.42, 0.02, 0.14, MAT.escuro, chefe ? 0 : 0, 0.8, 0.18, false));  // teclado
  const cadeira = new THREE.Group(); cadeira.position.z = prof / 2 + 0.42;
  cadeira.add(caixa(0.5, 0.08, 0.48, MAT.cinza, 0, 0.47, 0), caixa(0.5, chefe ? 0.85 : 0.6, 0.07, MAT.cinza, 0, chefe ? 0.92 : 0.8, 0.24),
              cilindro(0.035, 0.035, 0.44, MAT.cromo, 0, 0.22, 0, 8), cilindro(0.25, 0.25, 0.03, MAT.escuro, 0, 0.02, 0, 12));
  g.add(cadeira);
  const pilha = new THREE.Group(); pilha.position.set(-larg / 2 + 0.28, 0.79, 0.12); g.add(pilha);
  grupo.add(g);
  return { g, telas, pilha, assento: new THREE.Vector3(x, 0, z + prof / 2 + 0.42), visita: new THREE.Vector3(x - larg / 2 - 0.55, 0, z + 0.35) };
}
function empilhar(pilha, quantos) {
  // uma fita por corte na mesa, ate 8: acima disso a torre nao diz mais nada que o numero nao diga
  const quer = Math.min(quantos || 0, 8);
  while (pilha.children.length > quer) pilha.remove(pilha.children.at(-1));
  while (pilha.children.length < quer) {
    const f = caixa(0.3, 0.06, 0.2, MAT.fita, 0, pilha.children.length * 0.065 + 0.03, 0, false);
    f.rotation.y = (pilha.children.length % 3 - 1) * 0.2; pilha.add(f);
  }
}
function planta(grupo, x, z) {
  grupo.add(cilindro(0.24, 0.18, 0.42, MAT.vaso, x, 0.21, z, 10));
  for (let i = 0; i < 5; i++) {
    const folha = new THREE.Mesh(new THREE.ConeGeometry(0.15, 0.95 + i * 0.1, 5), MAT.planta);
    folha.position.set(x + Math.cos(i * 1.26) * 0.13, 0.9 + i * 0.05, z + Math.sin(i * 1.26) * 0.13);
    folha.rotation.set(Math.sin(i * 1.26) * 0.35, 0, -Math.cos(i * 1.26) * 0.35); folha.castShadow = true; grupo.add(folha);
  }
}
function estante(grupo, x, z, larg = 2) {
  grupo.add(caixa(larg, 1.7, 0.32, MAT.nogueira, x, 0.85, z));
  const lombadas = [0xb3262b, 0x1f5fae, 0xd4af5a, 0x2f7a4a, 0xece6da, 0x7a2f6b];
  for (let n = 0; n < 3; n++) for (let i = 0; i < larg / 0.14 - 1; i++)
    grupo.add(caixa(0.1, 0.3 + (i * 7 % 3) * 0.04, 0.2, mat(lombadas[(i + n * 2) % lombadas.length]), x - larg / 2 + 0.14 + i * 0.14, 0.42 + n * 0.5, z + 0.1, false));
}
function sofa(grupo, x, z, giro = 0, larg = 2.2) {
  const g = new THREE.Group(); g.position.set(x, 0, z); g.rotation.y = giro;
  g.add(caixa(larg, 0.4, 0.85, MAT.sofa, 0, 0.26, 0), caixa(larg, 0.5, 0.2, MAT.sofa, 0, 0.62, -0.33),
        caixa(0.2, 0.52, 0.85, MAT.sofa, -larg / 2 + 0.1, 0.4, 0), caixa(0.2, 0.52, 0.85, MAT.sofa, larg / 2 - 0.1, 0.4, 0));
  grupo.add(g);
}
function sinuca(grupo, x, z) {
  grupo.add(caixa(2.5, 0.16, 1.4, MAT.nogueira, x, 0.82, z), caixa(2.3, 0.02, 1.2, MAT.feltro, x, 0.91, z, false));
  for (const [dx, dz] of [[-1, -0.5], [1, -0.5], [-1, 0.5], [1, 0.5]]) grupo.add(caixa(0.14, 0.76, 0.14, MAT.nogueira, x + dx, 0.38, z + dz));
  const cores = [0xf2efe8, 0xd4af5a, 0xb3262b, 0x1f5fae, 0x17191e, 0x2f7a4a];
  cores.forEach((c, i) => { const b = new THREE.Mesh(new THREE.SphereGeometry(0.045, 10, 8), mat(c, { roughness: 0.3 }));
                           b.position.set(x - 0.7 + (i * 37 % 14) / 10, 0.965, z - 0.35 + (i * 53 % 7) / 10); grupo.add(b); });
}
function luminaria(grupo, x, z) {  // pendente aceso: da o tom quente de dentro sem custar uma luz de verdade
  grupo.add(caixa(0.5, 0.1, 0.5, MAT.luz, x, 2.9, z, false));
}
function placa(texto, cor = "#d4af5a", sub = "") {
  const t = tela(512, 128, (g, l, a) => {
    g.fillStyle = "#0b0f18e6"; g.beginPath(); g.roundRect(6, 6, l - 12, a - 12, 26); g.fill();
    g.fillStyle = cor; g.beginPath(); g.arc(46, a / 2, 13, 0, 7); g.fill();
    g.fillStyle = "#f1ece0"; g.textBaseline = "middle"; g.font = `700 ${sub ? 44 : 50}px system-ui, "Segoe UI", sans-serif`;
    g.fillText(texto.length > 14 ? texto.slice(0, 13) + "…" : texto, 74, sub ? 48 : a / 2 + 2);
    if (sub) { g.font = "500 26px system-ui, sans-serif"; g.fillStyle = cor; g.fillText(sub, 76, 94); }
  });
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: t, depthTest: false, toneMapped: false }));
  s.scale.set(3.4, 0.85, 1); s.renderOrder = 5;
  return s;
}

// ----------------------------------------------------------------- pessoas
const PELES = [0xf1c9a5, 0xd9a777, 0xb9835a, 0x8d5a3b, 0x6b4028], CABELOS = [0x1c1410, 0x3b2616, 0x6b4a2c, 0xb08a4a, 0x8a8a8a, 0x101010];
const ROUPAS = [0x2f4b7c, 0x7c2f3a, 0x2f6b55, 0x5a4a8a, 0x8a6a2f, 0x3a3f4a, 0xb85c38, 0x2a6f8f];
function pessoa(id, chefe = false) {
  const s = semente(id), roupa = mat(chefe ? 0x1b2436 : ROUPAS[s % ROUPAS.length]), pele = mat(PELES[(s >>> 3) % PELES.length], { roughness: 0.6 });
  const g = new THREE.Group(), corpo = new THREE.Group(); g.add(corpo);
  corpo.add(caixa(0.44, 0.58, 0.26, roupa, 0, 1.16, 0));
  if (chefe) corpo.add(caixa(0.14, 0.42, 0.02, mat(0xf4f1ea), 0, 1.2, 0.135, false), caixa(0.05, 0.36, 0.02, mat(0xb3262b), 0, 1.18, 0.148, false));
  const cabeca = new THREE.Group(); cabeca.position.y = 1.62; corpo.add(cabeca);
  cabeca.add(caixa(0.28, 0.3, 0.28, pele, 0, 0, 0));
  const cabelo = mat(CABELOS[(s >>> 12) % CABELOS.length]);
  cabeca.add(caixa(0.3, 0.1, 0.3, cabelo, 0, 0.17, 0), caixa(0.3, 0.2, 0.08, cabelo, 0, 0.06, -0.12));
  const membro = (x, y, material, comp, larg) => {
    const p = new THREE.Group(); p.position.set(x, y, 0);
    p.add(caixa(larg, comp, larg, material, 0, -comp / 2, 0)); corpo.add(p); return p;
  };
  const bracoE = membro(-0.29, 1.4, roupa, 0.56, 0.12), bracoD = membro(0.29, 1.4, roupa, 0.56, 0.12);
  bracoE.add(caixa(0.1, 0.1, 0.1, pele, 0, -0.6, 0, false)); bracoD.add(caixa(0.1, 0.1, 0.1, pele, 0, -0.6, 0, false));
  const calca = mat(0x1d2028), pernaE = membro(-0.12, 0.87, calca, 0.87, 0.16), pernaD = membro(0.12, 0.87, calca, 0.87, 0.16);
  const fita = caixa(0.3, 0.06, 0.2, MAT.fita, 0, 1.05, 0.34, false); fita.visible = false; corpo.add(fita);
  return { id, g, corpo, cabeca, bracoE, bracoD, pernaE, pernaD, fita, fase: (s % 628) / 100,
           estado: "sentado", relogio: 3 + (s % 1200) / 100, caminho: [], aoChegar: null, humor: "normal", ocupado: false };
}

// ------------------------------------------------------------- montagem do predio
let predio = null, salas = {}, gente = [], telao = null, mapa = null, assinatura = "", dados = null;
const ZA0 = -17, ZA1 = -10, ZB0 = -5.6, ZM = -7.8, PT = 6.2, LT = 7.2, RAIA = 2.6, LARGURA = 48.5;

function sala(id, x0, z0, x1, z1, tipoDePiso, nome, portaSul) {
  const cx = (x0 + x1) / 2, cz = (z0 + z1) / 2, vao = 1.5;
  piso(predio, tipoDePiso, x0, z0, x1, z1);
  const zPorta = portaSul ? z1 : z0, zFundo = portaSul ? z0 : z1, sinal = portaSul ? 1 : -1;
  muro(predio, x0, zFundo, x1, zFundo); muro(predio, x0, z0, x0, z1); muro(predio, x1, z0, x1, z1);
  muro(predio, x0, zPorta, cx - vao / 2, zPorta); muro(predio, cx + vao / 2, zPorta, x1, zPorta);
  luminaria(predio, cx, cz);
  const rotulo = placa(nome); rotulo.position.set(cx, 3.3, cz); predio.add(rotulo);
  const alvo = new THREE.Mesh(new THREE.BoxGeometry(x1 - x0, 2.2, z1 - z0), new THREE.MeshBasicMaterial({ visible: false }));
  alvo.position.set(cx, 1.1, cz); alvo.userData.sala = id; predio.add(alvo);
  const s = { id, cx, cz, x0, z0, x1, z1, rotulo, alvo, nome, mesas: [], gente: [], pontos: [],
              portaDentro: new THREE.Vector3(cx, 0, zPorta - sinal * 0.8), portaFora: new THREE.Vector3(cx, 0, zPorta + sinal * 0.9) };
  salas[id] = s;
  return s;
}

function montar(q) {
  if (predio) { cena.remove(predio); predio.traverse(o => { o.geometry?.dispose(); }); }
  predio = new THREE.Group(); salas = {}; gente = []; baloes.replaceChildren();
  const n = q.times.length, filas = Math.max(1, Math.ceil(n / 4)), passoZ = PT + 2.4;
  const X0 = -LARGURA / 2, X1 = LARGURA / 2, XT = X0 + RAIA, zFim = ZB0 + (filas - 1) * passoZ + PT;
  const xOficinas = XT + 4 * LT;  // onde acabam as salas dos times
  mapa = { X0, X1, zFim, raia: X0 + RAIA / 2, centro: new THREE.Vector3(0, 0.6, (ZA0 + zFim) / 2) };

  // jardim a noite, calcada ate o estacionamento e o piso de madeira do predio inteiro
  piso(predio, "grama", -150, -150, 150, 150, -0.05);
  predio.add(caixa(LARGURA + 0.6, 0.3, zFim - ZA0 + 0.6, MAT.rodape, 0, -0.16, mapa.centro.z, false));
  piso(predio, "madeira", X0, ZA0, X1, zFim, 0.004);
  piso(predio, "calcada", X1, ZM - 1.3, X1 + 16, ZM + 1.3, 0.0);
  predio.add(caixa(18, 0.04, 14, MAT.asfalto, X1 + 25, 0, ZM, false));
  for (let i = 0; i < 5; i++) predio.add(caixa(0.12, 0.05, 4.4, MAT.branco, X1 + 18 + i * 3.4, 0.01, ZM - 3.6, false));
  [[0xb3262b, 19.7], [0xece6da, 23.1], [0x2f4b7c, 29.9]].forEach(([cor, dx]) => {
    predio.add(caixa(1.9, 0.7, 4, mat(cor, { roughness: 0.35, metalness: 0.4 }), X1 + dx, 0.55, ZM - 3.6), caixa(1.7, 0.55, 2.1, MAT.escuro, X1 + dx, 1.15, ZM - 3.4));
  });
  for (let i = 0; i < 5; i++) {  // postes da calcada
    const x = X1 + 2 + i * 3.4;
    predio.add(cilindro(0.05, 0.07, 2.6, MAT.escuro, x, 1.3, ZM + 1.7, 8)); const lamp = new THREE.Mesh(new THREE.SphereGeometry(0.2, 10, 8), MAT.luz); lamp.position.set(x, 2.7, ZM + 1.7); predio.add(lamp);
  }
  // pinheiros em volta, fora do predio, da calcada e do estacionamento
  const copas = new THREE.InstancedMesh(new THREE.ConeGeometry(1.5, 5.2, 7), MAT.pinheiro, 90), troncos = new THREE.InstancedMesh(new THREE.CylinderGeometry(0.2, 0.26, 1.4, 6), MAT.tronco, 90);
  const m = new THREE.Matrix4(); let postos = 0, tentativas = 0;
  while (postos < 90 && tentativas++ < 2000) {
    const x = (Math.random() - 0.5) * 170, z = mapa.centro.z + (Math.random() - 0.5) * 150, e = 0.7 + Math.random() * 0.8;
    const noPredio = x > X0 - 4 && x < X1 + 4 && z > ZA0 - 4 && z < zFim + 4, naCalcada = x > X1 && x < X1 + 36 && Math.abs(z - ZM) < 9;
    // nada entre a camera (sul e leste) e o predio: arvore ali taparia as salas
    const naFrente = z > zFim && x > X0 - 10 && x < X1 + 30;
    if (noPredio || naCalcada || naFrente) continue;
    m.compose(new THREE.Vector3(x, 1.4 + 2.6 * e, z), new THREE.Quaternion(), new THREE.Vector3(e, e, e)); copas.setMatrixAt(postos, m);
    m.compose(new THREE.Vector3(x, 0.7, z), new THREE.Quaternion(), new THREE.Vector3(e, 1, e)); troncos.setMatrixAt(postos, m); postos++;
  }
  copas.count = troncos.count = postos; copas.castShadow = true; predio.add(copas, troncos);

  // ala norte: qualidade, compliance, gerencia, diretoria e o CEO, na ordem em que o corte sobe; lounge na ponta
  let x = X0;
  for (const [id, larg, tipo] of [["qualidade", 6.5, "azul"], ["compliance", 6.5, "azul"], ["gerente", 7, "azul"], ["diretor", 7.5, "madeira"], ["ceo", 10, "madeira"]]) {
    const info = id === "ceo" ? q.ceo : q.gestao.find(g => g.id === id);
    const s = sala(id, x, ZA0, x + larg, ZA1, tipo, id === "ceo" ? "CEO" : info.cargo.split(" ")[0], true);
    const me = mesa(predio, s.cx, s.cz - 0.9, true); s.mesas.push(me);
    const p = pessoa(id, true); p.sala = s; p.mesa = me; p.cargo = id; s.gente.push(p); gente.push(p);
    estante(predio, s.cx - larg / 2 + 1.4, ZA0 + 0.32, 2.2); planta(predio, x + larg - 0.7, ZA0 + 0.7);
    if (id === "ceo" || id === "diretor") piso(predio, "carpete", s.cx - 2.4, s.cz - 2.2, s.cx + 2.4, s.cz + 1.6, 0.02);
    if (id === "ceo") { sofa(predio, s.cx + 3.3, s.cz + 1.8, -Math.PI / 2); predio.add(cilindro(0.45, 0.45, 0.06, MAT.nogueira, s.cx + 2, 0.4, s.cz + 1.8, 16)); }
    x += larg;
  }
  const lounge = sala("lounge", x, ZA0, X1, ZA1, "madeira", "Lounge", true);
  sinuca(predio, lounge.cx - 2.6, lounge.cz - 1.2); sinuca(predio, lounge.cx + 2.6, lounge.cz - 1.2);
  sofa(predio, lounge.cx - 3.6, lounge.cz + 2.2, Math.PI); piso(predio, "carpete", lounge.cx + 1, lounge.cz + 1, lounge.cx + 4.8, lounge.cz + 3, 0.02);
  sofa(predio, lounge.cx + 3, lounge.cz + 2.3, Math.PI, 2.8); planta(predio, X1 - 0.7, ZA0 + 0.7); planta(predio, x + 0.7, ZA0 + 0.7);
  lounge.pontos = [[-2.6, 0.3], [2.6, 0.3], [-4.2, -1.2], [4.2, -1.2], [0, 1.2]].map(([dx, dz]) => new THREE.Vector3(lounge.cx + dx, 0, lounge.cz + dz));

  // salas dos times: carpete vermelho, tres mesas em linha e a do lider perto da porta
  q.times.forEach((t, i) => {
    const col = i % 4, fila = Math.floor(i / 4), x0 = XT + col * LT, z0 = ZB0 + fila * passoZ;
    const s = sala(t.chave, x0, z0, x0 + LT, z0 + PT, "carpete", curto(t.canal), false);
    s.fila = fila; s.time = true;
    [[-2.2, 0.9], [0, 0.9], [2.2, 0.9], [2, -1.7]].forEach(([dx, dz], k) => {
      const me = mesa(predio, s.cx + dx, s.cz + dz, k === 3); s.mesas.push(me);
      const info = t.pessoas[k], p = pessoa(info.id); p.sala = s; p.mesa = me; p.cargo = info.papel; s.gente.push(p); gente.push(p);
    });
    planta(predio, x0 + 0.6, z0 + 0.6);
  });
  // fila de times incompleta: fecha o lado sul do espaco vazio, senao o predio fica aberto para o jardim
  for (let f = 0; f < filas; f++) {
    const naFila = Math.max(0, Math.min(4, n - f * 4)), zSul = ZB0 + f * passoZ + PT;
    if (naFila < 4) muro(predio, XT + naFila * LT, zSul, xOficinas, zSul);
  }
  // sala de reuniao e cozinha na mesma linha da primeira fila de times
  const reuniao = sala("reuniao", xOficinas, ZB0, X1 - 11, ZB0 + PT, "azul", "Reunião", false);
  predio.add(caixa(1.3, 0.07, 3.4, MAT.nogueira, reuniao.cx, 0.76, reuniao.cz + 0.5), caixa(0.5, 0.74, 2.6, MAT.escuro, reuniao.cx, 0.37, reuniao.cz + 0.5));
  for (const lado of [-1, 1]) for (let k = 0; k < 3; k++) predio.add(caixa(0.45, 0.5, 0.45, MAT.cinza, reuniao.cx + lado * 1.1, 0.25, reuniao.cz - 0.5 + k));
  // o telao fica na parede norte, virado para o sul: e o lado que a camera enxerga
  telao = new THREE.Mesh(new THREE.PlaneGeometry(2, 1), new THREE.MeshBasicMaterial({ color: 0xffffff, toneMapped: false }));
  telao.position.set(reuniao.cx + 1.9, 1.15, ZB0 + 0.15); predio.add(telao, caixa(2.14, 1.14, 0.06, MAT.escuro, reuniao.cx + 1.9, 1.15, ZB0 + 0.11, false));
  const cozinha = sala("cozinha", X1 - 11, ZB0, X1, ZB0 + PT, "frio", "Cozinha", false);
  const zBancada = ZB0 + PT - 0.5;
  predio.add(caixa(7.4, 0.9, 0.7, MAT.branco, cozinha.cx - 1.2, 0.45, zBancada), caixa(7.5, 0.05, 0.75, MAT.nogueira, cozinha.cx - 1.2, 0.93, zBancada, false),
             caixa(1, 1.85, 0.8, MAT.cromo, X1 - 0.9, 0.93, zBancada - 0.05), caixa(0.45, 0.42, 0.4, MAT.escuro, cozinha.cx - 2.2, 1.17, zBancada),
             caixa(0.08, 0.04, 0.04, MAT.luz, cozinha.cx - 2.2, 1.3, zBancada - 0.21, false));
  predio.add(cilindro(0.9, 0.9, 0.06, MAT.tampo, cozinha.cx + 2.6, 0.78, cozinha.cz - 0.9, 20), cilindro(0.08, 0.3, 0.76, MAT.cromo, cozinha.cx + 2.6, 0.38, cozinha.cz - 0.9, 10));
  for (let k = 0; k < 4; k++) predio.add(cilindro(0.2, 0.2, 0.5, MAT.cinza, cozinha.cx + 2.6 + Math.cos(k * 1.57) * 1.3, 0.25, cozinha.cz - 0.9 + Math.sin(k * 1.57) * 1.3, 10));
  cozinha.pontos = [[-3.4, 1.4], [-2.2, 1.4], [-1, 1.4], [0.4, 1.4], [2.6, 0.9]].map(([dx, dz]) => new THREE.Vector3(cozinha.cx + dx, 0, cozinha.cz + dz));

  // paredes de fora: corredor, raia dos times e a entrada, que abre para a calcada
  muro(predio, X0, ZA1, X0, zFim); muro(predio, X1, ZA1, X1, ZM - 1.3); muro(predio, X1, ZM + 1.3, X1, ZB0);
  if (filas > 1) {
    muro(predio, X0, zFim, xOficinas, zFim); muro(predio, xOficinas, ZB0 + PT, xOficinas, zFim);
    // o canto que sobra ao lado das filas de baixo vira um deque aberto
    sofa(predio, xOficinas + 5, ZB0 + PT + 3.2, 0, 2.8); planta(predio, xOficinas + 2, ZB0 + PT + 1.6); planta(predio, X1 - 1.5, zFim - 1.5);
  } else muro(predio, X0, zFim, X0 + RAIA, zFim);
  for (let k = 0; k < 4; k++) { planta(predio, X0 + 6 + k * 10, ZA1 + 0.6); luminaria(predio, X0 + 5 + k * 12, ZM); }
  piso(predio, "azul", X0 + 3, ZM - 0.7, X1 - 3, ZM + 0.7, 0.008);  // passadeira do corredor

  for (const p of gente) { predio.add(p.g); sentar(p); }
  cena.add(predio);
  const largura = LARGURA, profundidade = zFim - ZA0, alcance = Math.max(largura, profundidade) * 0.75;
  teto.position.set(mapa.centro.x + 8, 40, mapa.centro.z + 10); teto.target.position.copy(mapa.centro);
  Object.assign(teto.shadow.camera, { left: -alcance, right: alcance, top: alcance, bottom: -alcance, far: 120 });
  teto.shadow.camera.updateProjectionMatrix();
  mapa.raio = Math.hypot(largura, profundidade) / 2;
  $("comodos").replaceChildren(...[["", "Visão geral"], ["times", "Times"], ["gestao", "Gestão"], ["ceo", "Diretoria"], ["reuniao", "Reunião"], ["cozinha", "Cozinha"], ["lounge", "Lounge"]]
    .map(([id, nome]) => { const b = el("button", { type: "button", textContent: nome, onclick: () => irPara(id) }); b.dataset.id = id; b.setAttribute("aria-pressed", String(!id)); return b; }));
  ajustar(); enquadrar();
}

function enquadrar() {
  // afasta a camera ate o predio inteiro caber, na largura ou na altura, o que apertar primeiro
  // em tela larga os paineis laterais cobrem as bordas: o predio tem de caber na faixa livre do meio
  const livre = palco.clientWidth > 1050 ? (palco.clientWidth - 620) / palco.clientWidth : 1;
  const vertical = THREE.MathUtils.degToRad(camera.fov) / 2, horizontal = Math.atan(Math.tan(vertical) * camera.aspect * livre);
  // o predio e mais largo que fundo: quando quem aperta e a largura (tela estreita) precisa de mais folga
  const dist = mapa.raio / Math.sin(Math.min(vertical, horizontal)) * (horizontal < vertical ? 1.02 : 0.78);
  controles.target.copy(mapa.centro);
  camera.position.copy(mapa.centro).add(new THREE.Vector3(0.2, 0.88, 0.62).normalize().multiplyScalar(dist));
  controles.maxDistance = dist * 1.7;
}

// ------------------------------------------------------------- vida das pessoas
function sentar(p) {
  p.estado = "sentado"; p.g.position.copy(p.mesa.assento); p.g.position.y = -0.36; p.g.rotation.y = Math.PI;
  p.pernaE.rotation.x = p.pernaD.rotation.x = -1.45; p.fita.visible = false; p.onde = p.sala;
}
function rota(de, para, ate) {
  // anda sempre por porta e corredor. "de" e a sala em que a pessoa esta, ou null quando esta no corredor
  const pts = [], saida = s => { pts.push(s.portaDentro.clone(), s.portaFora.clone()); if (s.fila) pts.push(new THREE.Vector3(mapa.raia, 0, s.portaFora.z), new THREE.Vector3(mapa.raia, 0, ZM)); else pts.push(new THREE.Vector3(s.portaFora.x, 0, ZM)); };
  if (de !== para) {
    if (de) saida(de);
    if (para) { const volta = []; const guardado = pts.splice(0); saida(para); volta.push(...pts.splice(0).reverse()); pts.push(...guardado, ...volta); }
  }
  pts.push(ate.clone());
  return pts;
}
function andarAte(p, para, ponto, aoChegar) {
  if (p.estado === "sentado") { p.g.position.y = 0; p.pernaE.rotation.x = p.pernaD.rotation.x = 0; }
  p.caminho = rota(p.onde, para, ponto); p.onde = para; p.estado = "andando"; p.aoChegar = aoChegar;
}
function voltar(p) { andarAte(p, p.sala, p.mesa.assento, () => sentar(p)); }
function falar(p, texto, tom = "", segundos = 3.6) {
  p.balao?.remove();
  p.balao = el("div", { className: "balao " + tom, textContent: texto }); baloes.append(p.balao);
  p.balaoAte = performance.now() + segundos * 1000;
}
const ritmo = humor => ({ animado: 1.45, normal: 1, cauteloso: 0.78, pressao: 0.62 }[humor] ?? 1);

function pausa(p) {
  // quem esta com trabalho na mao nao levanta. Dos outros, time animado circula mais e time sob pressao quase nao sai.
  const vontade = { animado: 0.6, normal: 0.42, cauteloso: 0.25, pressao: 0.1 }[p.humor] ?? 0.4;
  p.relogio = (8 + Math.random() * 16) / ritmo(p.humor);
  if (p.ocupado || p.entregando || Math.random() > vontade) return;
  const sorte = Math.random(), comodo = sorte < 0.5 ? salas.cozinha : sorte < 0.82 ? salas.lounge : null;
  if (comodo) {
    andarAte(p, comodo, um(comodo.pontos), () => { p.estado = "parado"; p.relogio = 5 + Math.random() * 4; p.g.lookAt(comodo.cx, 0, comodo.cz + (comodo === salas.cozinha ? 3 : -1)); });
    falar(p, um(PAUSAS), "", 2.2);
  } else {
    const colegas = p.sala.gente.filter(c => c !== p && c.estado === "sentado");
    if (!colegas.length) return;
    const c = um(colegas);
    andarAte(p, c.sala, c.mesa.visita, () => { p.estado = "parado"; p.relogio = 4; p.g.lookAt(c.g.position.x, 0, c.g.position.z); });
  }
}

const filaDeEntregas = [];
function entregar(de, para, texto, depois) {
  // quem valida a etapa leva a fita pessoalmente ate a mesa de quem valida a seguinte
  if (!de || !para || calmo) { depois?.(); return; }
  if (de.entregando) { filaDeEntregas.push([de, para, texto, depois]); return; }
  de.entregando = true; de.fita.visible = true; falar(de, texto);
  andarAte(de, para.sala, para.mesa.visita, () => {
    de.fita.visible = false; de.entregando = false; depois?.();
    de.estado = "parado"; de.relogio = 0.8;
    const i = filaDeEntregas.findIndex(f => f[0] === de);
    if (i >= 0) { const [a, b, t, d] = filaDeEntregas.splice(i, 1)[0]; setTimeout(() => entregar(a, b, t, d), 900); }
  });
  de.fita.visible = true;
}
function comemorar(sala) { for (const p of sala.gente) { if (p.estado === "sentado" || p.estado === "parado") { p.estado = "festa"; p.relogio = 2.6; p.g.position.y = 0; p.pernaE.rotation.x = p.pernaD.rotation.x = 0; } } }

const ORDEM = ["lider_time", "qualidade", "compliance", "gerente", "diretor", "ceo"];
const dono = (etapa, chave) => etapa === "lider_time" ? salas[chave]?.gente[3] : salas[etapa]?.gente[0];
const AVISO = { qualidade: "Pra qualidade", compliance: "Pro compliance", gerente: "Pra gerência", diretor: "Pro diretor", ceo: "Pro CEO" };
let anteriores = null;
function reagir(cortes) {
  // compara com a leitura anterior: cada mudanca de etapa vira alguem atravessando o escritorio com a fita
  const agora = new Map(cortes.map(c => [c.id, c]));
  if (anteriores) for (const c of cortes) {
    const antes = anteriores.get(c.id), s = salas[c.canal_chave];
    const de = antes ? ORDEM.indexOf(antes.etapa) : -1, ate = ORDEM.indexOf(c.etapa);
    if (c.etapa === "aprovado" && antes?.etapa !== "aprovado") {
      falar(salas.ceo.gente[0], "Aprovado", "bom", 4);
      if (s) { comemorar(s); falar(s.gente[3], "Aprovou!", "bom", 4); }
    } else if (c.etapa === "descartado" && antes && antes.etapa !== "descartado") {
      const quem = dono(antes.etapa, c.canal_chave); if (quem) falar(quem, "Barrado", "ruim", 4);
    } else if (ate > de) {
      const passos = [];
      if (!antes && s) passos.push([s.gente[1], s.gente[3], "Pro líder"]);
      for (let i = Math.max(de, 0); i < ate; i++) passos.push([dono(ORDEM[i], c.canal_chave), dono(ORDEM[i + 1], c.canal_chave), AVISO[ORDEM[i + 1]]]);
      const seguir = k => { if (k < passos.length) entregar(...passos[k], () => seguir(k + 1)); };
      seguir(0);
    }
  }
  anteriores = agora;
}
const PAPEL = { radar: 0, edicao: 1, redacao: 2, lider: 3 };
let vistos = null;
function narrar(eventos) {
  // cada linha nova do diario vira um balao em cima de quem fez aquilo de verdade.
  // Na primeira leitura so anota o que ja existia: abrir a tela nao pode reencenar o dia inteiro.
  const marca = e => e.quando + "|" + e.chave + "|" + e.papel + "|" + e.texto;
  const novos = vistos ? eventos.filter(e => !vistos.has(marca(e))) : [];
  vistos = new Set(eventos.map(marca));
  for (const e of novos.slice(-6)) {
    const p = e.chave === "empresa" ? salas[e.papel]?.gente[0] : salas[e.chave]?.gente[PAPEL[e.papel]];
    if (p) falar(p, e.texto.length > 44 ? e.texto.slice(0, 43) + "…" : e.texto, /barrou|descartou|reprovou/.test(e.texto) ? "ruim" : "", 5);
  }
}

// ------------------------------------------------------------------ dados
let selecionada = null, ocupadoComExpediente = false, expedienteNaTela = null, timesNoSeletor = null;
function aplicar(q) {
  dados = q;
  const nova = JSON.stringify(q.times.map(t => [t.chave, t.pessoas.map(p => p.id)]));
  if (nova !== assinatura) { assinatura = nova; selecionada = null; ficha.hidden = true; anteriores = null; montar(q); }
  for (const t of q.times) {
    const s = salas[t.chave]; if (!s) continue;
    s.info = t;
    const cor = { animado: "#3ddc84", normal: "#d4af5a", cauteloso: "#f0a63a", pressao: "#ff5d5d" }[t.humor.nivel], sub = t.ligado ? "time " + t.humor.rotulo : "sem expediente";
    if (s.rotuloDe !== cor + sub) { s.rotuloDe = cor + sub; s.rotulo.material.map.dispose(); s.rotulo.material.map = placa(curto(t.canal), t.ligado ? cor : "#5b636d", sub).material.map; }
    s.gente.forEach((p, k) => {
      p.humor = t.humor.nivel; p.ocupado = Boolean(t.pessoas[k].fazendo); p.fazendo = t.pessoas[k].fazendo;
      // tela acesa so para quem esta com trabalho na mao; no lider, quando ha corte esperando por ele
      const ligada = p.ocupado || (k === 3 && t.fila > 0);
      s.mesas[k].telas.forEach(tl => { tl.material.map = ligada ? TELAS[t.humor.nivel] : TELAS.desligada; });
      empilhar(s.mesas[k].pilha, k === 3 ? t.fila : 0);
    });
  }
  for (const g of [...q.gestao, { id: "ceo", ...q.ceo }]) {
    const s = salas[g.id]; s.info = g; const p = s.gente[0];
    p.ocupado = g.fila > 0 || Boolean(g.fazendo); p.fazendo = g.fazendo;
    s.mesas[0].telas.forEach(tl => { tl.material.map = p.ocupado ? TELAS.gestao : TELAS.desligada; }); empilhar(s.mesas[0].pilha, g.fila);
  }
  reagir(q.cortes); narrar(q.eventos);
  telao.material.map?.dispose();
  telao.material.map = tela(512, 256, (g, l, a) => {
    g.fillStyle = "#04070c"; g.fillRect(0, 0, l, a); g.textBaseline = "top";
    g.fillStyle = "#d4af5a"; g.font = "700 30px system-ui, sans-serif"; g.fillText("PAUTA DE HOJE", 24, 20);
    g.fillStyle = "#f1ece0"; g.font = "600 40px system-ui, sans-serif";
    g.fillText(q.times.reduce((s, t) => s + t.feitos_hoje, 0) + " cortes produzidos", 24, 78);
    g.fillStyle = q.ceo.fila ? "#ff5d5d" : "#3ddc84"; g.fillText(q.ceo.fila + " na mesa do CEO", 24, 136);
    g.fillStyle = "#9aa3b2"; g.font = "500 28px system-ui, sans-serif"; g.fillText("CEO " + q.ceo.hoje, 24, 198);
  });
  telao.material.needsUpdate = true;

  $("marca").textContent = q.empresa; document.title = "Escritório · " + q.empresa;
  $("hora").textContent = q.agora.slice(11, 16);
  $("pendentes").hidden = !q.ceo.fila; $("pendentes").textContent = q.ceo.fila;
  const todos = q.times.flatMap(t => t.pessoas), trabalhando = todos.filter(p => p.fazendo).length + q.gestao.filter(g => g.fazendo).length;
  const cartao = (n, rotulo, alerta = false) => el("div", { className: alerta ? "alerta" : "" }, [el("b", { textContent: String(n) }), document.createTextNode(rotulo)]);
  $("placar").replaceChildren(cartao(trabalhando + "/" + (todos.length + q.gestao.length), "agentes ativos"), cartao(q.times.filter(t => t.ligado).length, "lives vigiadas"),
                              cartao(q.times.reduce((s, t) => s + t.feitos_hoje, 0), "cortes hoje"), cartao(q.ceo.fila, "na sua mesa", q.ceo.fila > 0));
  // o cartao so e refeito quando o estado muda: trocar o botao a cada leitura engoliria o clique do CEO
  const estadoDoExpediente = q.vigia.rodando + "|" + q.vigia.desde;
  if (!ocupadoComExpediente && estadoDoExpediente !== expedienteNaTela) {
    expedienteNaTela = estadoDoExpediente;
    const aberto = q.vigia.rodando, botao = el("button", { type: "button", className: aberto ? "fechar" : "", textContent: aberto ? "Fechar o expediente" : "Abrir o expediente", onclick: () => expediente(aberto ? "fechar" : "abrir") });
    botao.disabled = DEMO;
    $("expediente").replaceChildren(el("h2", { textContent: "Expediente" }),
      el("p", { textContent: DEMO ? "Demonstração: os dados desta tela são simulados." : aberto ? "Aberto desde " + (q.vigia.desde || "").slice(11, 16) + ". Os times estão acompanhando as lives e mandando cortes para a sua mesa."
                                                         : "Fechado. Ninguém está acompanhando as lives agora." }), botao);
  }
  const linha = (p, canal) => el("div", { className: "agente" }, [el("i", { textContent: p.nome[0], style: "background:" + corDe(p.id || p.nome) }),
    el("span", { textContent: p.nome + " · " + p.cargo }), el("small", { className: p.fazendo ? "ativo" : "", textContent: p.fazendo || "aguardando", title: p.fazendo || "" })]);
  $("agentes").replaceChildren(
    ...q.times.map(t => el("div", { className: "time" }, [el("h3", { onclick: () => focar(t.chave) }, [el("span", { className: "ponto " + (t.ligado ? t.humor.nivel : "fora") }), document.createTextNode("Time " + curto(t.canal))]),
                                                         ...t.pessoas.map(p => linha(p))])),
    el("div", { className: "time" }, [el("h3", { onclick: () => irPara("gestao") }, [el("span", { className: "ponto" }), document.createTextNode("Gestão e diretoria")]), ...q.gestao.map(g => linha(g))]));
  // o seletor de times so e refeito quando a lista de times muda, para nao desfazer a escolha do CEO a cada leitura
  const opcoes = JSON.stringify(q.times.map(t => [t.chave, t.canal]));
  if (opcoes !== timesNoSeletor) {
    timesNoSeletor = opcoes; const escolhido = $("paraTime").value;
    $("paraTime").replaceChildren(el("option", { value: "", textContent: "Time do próprio canal" }),
                                  ...q.times.map(t => el("option", { value: t.chave, textContent: "Time " + curto(t.canal) })));
    $("paraTime").value = [...$("paraTime").options].some(o => o.value === escolhido) ? escolhido : "";
  }
  const ROTULO = { pendente: "na fila", em_andamento: "cortando", feito: "pronto", erro: "erro" };
  $("fila").replaceChildren(...[...(q.pedidos || [])].reverse().slice(0, 4).map(p => el("li", {}, [
    el("b", { className: p.situacao, textContent: ROTULO[p.situacao] || p.situacao }),
    el("span", { textContent: (p.detalhe ? p.detalhe + " · " : "") + p.url.replace(/^https?:\/\/(www\.)?/, ""), title: p.url + (p.detalhe ? " — " + p.detalhe : "") })])));
  if (!q.times.length) $("agentes").prepend(el("p", { className: "vazio", textContent: "Nenhum canal no canais.txt ainda." }));
  const feed = [...q.eventos].reverse();
  $("feed").replaceChildren(...(feed.length ? feed.map(e => el("li", {}, [el("time", { textContent: e.quando.slice(11, 19) }), el("b", { textContent: e.quem }), el("span", { textContent: e.texto })]))
                                            : [el("p", { className: "vazio", textContent: "Nada aconteceu ainda. Abra o expediente para os times começarem a acompanhar as lives." })]));
  const etapas = [{ id: "times", rotulo: "Times", n: q.times.reduce((s, t) => s + t.fila, 0) },
                  ...q.gestao.map(g => ({ id: g.id, rotulo: g.cargo.split(" ")[0], n: g.fila })), { id: "ceo", rotulo: "Você", n: q.ceo.fila }];
  $("esteira").replaceChildren(...etapas.flatMap((e, i) => {
    const b = el("button", { type: "button", className: e.id === "ceo" ? "voce" + (e.n ? " cheia" : "") : "", onclick: () => e.id === "times" ? irPara("times") : focar(e.id) },
                 [el("b", { textContent: String(e.n) }), document.createTextNode(e.rotulo)]);
    return i ? [el("i", { textContent: "›" }), b] : [b];
  }));
  if (selecionada) mostrarFicha(selecionada);
}

async function expediente(acao) {
  // enquanto o pedido esta no ar o cartao nao e redesenhado pela leitura periodica, senao o botao piscaria
  ocupadoComExpediente = true;
  const botao = $("expediente").querySelector("button"); botao.disabled = true; botao.textContent = acao === "abrir" ? "Abrindo…" : "Fechando…";
  try {
    const r = await fetch("/api/expediente", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ acao }) });
    if (!r.ok) { const erro = (await r.json().catch(() => ({}))).erro; botao.textContent = "Não deu: " + (erro || "erro"); await new Promise(f => setTimeout(f, 2500)); }
  } catch { botao.textContent = "Sem resposta do servidor"; await new Promise(f => setTimeout(f, 2500)); }
  ocupadoComExpediente = false; expedienteNaTela = null; atualizar();
}

$("passar").addEventListener("submit", async ev => {
  // o CEO passa um link: canal vira um time que acompanha; live (antiga ou no ar) entra na fila do time escolhido
  ev.preventDefault();
  const retorno = $("retorno"), botao = $("passar").querySelector("button");
  if (DEMO) { retorno.className = ""; retorno.textContent = "Na demonstração os links não são enviados."; return; }
  botao.disabled = true; retorno.className = ""; retorno.textContent = "Enviando…";
  try {
    const r = await fetch("/api/pedido", { method: "POST", headers: { "Content-Type": "application/json" },
                                           body: JSON.stringify({ url: $("link").value, time: $("paraTime").value, cortes: Number($("quantos").value) || 5 }) });
    const j = await r.json().catch(() => ({}));
    retorno.className = r.ok ? "" : "erro"; retorno.textContent = r.ok ? j.mensagem : "Não deu: " + (j.erro || "erro");
    if (r.ok) $("link").value = "";
  } catch { retorno.className = "erro"; retorno.textContent = "Sem resposta do servidor."; }
  botao.disabled = false; atualizar();
});

function mostrarFicha(id) {
  const s = salas[id]; if (!s?.info) { ficha.hidden = true; return; }
  const i = s.info, p = (txt, cls = "") => el("p", { textContent: txt, className: cls }), partes = [];
  const numeros = pares => el("div", { className: "numeros" }, pares.map(([n, r]) => el("div", {}, [el("b", { textContent: String(n) }), document.createTextNode(r)])));
  if (s.time) {
    partes.push(el("h2", { textContent: "Time " + curto(i.canal) }), p(i.canal + " · " + i.situacao),
                el("span", { className: "humor " + i.humor.nivel, textContent: "Time " + i.humor.rotulo }),
                p(i.humor.decisoes ? `${Math.round(i.humor.taxa * 100)}% de aprovação nas suas últimas ${i.humor.decisoes} decisões. Efeito: ${i.humor.efeito}.`
                                   : "Ainda sem decisões suas sobre este time."),
                numeros([[i.feitos_hoje, "feitos hoje"], [i.aprovados_hoje, "aprovados hoje"], [i.fila, "com o líder"]]));
    if (!i.autorizado) partes.push(p("Canal sem autorização do streamer: a postagem fica bloqueada.", "aviso"));
    partes.push(el("h3", { textContent: "Equipe" }), el("ul", {}, i.pessoas.map(x => el("li", {}, [document.createTextNode(x.nome + " · " + x.cargo), el("small", { textContent: x.fazendo || x.faz })]))));
    if (i.feedback.length) partes.push(el("h3", { textContent: "Retorno recente dos gestores" }), el("ul", {}, i.feedback.map(f => el("li", {}, [document.createTextNode(f.texto), el("small", { textContent: f.de })]))));
  } else {
    partes.push(el("h2", { textContent: i.nome }), p(id === "ceo" ? "Aprovador final: só o que você aprova pode ser postado." : i.cargo),
                numeros([[i.fila, id === "ceo" ? "esperando você" : "na mesa"]]), p("Hoje: " + i.hoje));
    if (i.fazendo) partes.push(p("Agora: " + i.fazendo));
    if (id === "ceo") partes.push(el("a", { href: "/", textContent: "Abrir a fila de aprovação" }));
  }
  const fechar = el("button", { type: "button", id: "fechar", textContent: "×", onclick: () => focar(null) });
  fechar.setAttribute("aria-label", "Fechar");
  ficha.replaceChildren(...partes, fechar); ficha.hidden = false;
}
let foco = null;
function mirar(x, z, distancia) {
  // leva o alvo da camera ate o comodo e aproxima, mantendo o angulo em que o CEO deixou a camera
  const alvo = new THREE.Vector3(x, 0.6, z), rumoDaCamera = camera.position.clone().sub(controles.target).normalize();
  foco = { alvo, posicao: alvo.clone().addScaledVector(rumoDaCamera, distancia), ate: performance.now() + 1100 };
}
function focar(id) {
  selecionada = id && salas[id]?.info ? id : null;
  if (!id || !salas[id]) { ficha.hidden = true; irPara(""); return; }
  if (selecionada) mostrarFicha(selecionada); else ficha.hidden = true;
  mirar(salas[id].cx, salas[id].cz, 30);
}
function irPara(id) {
  for (const b of $("comodos").children) b.setAttribute("aria-pressed", String(b.dataset.id === id));
  if (!id) { selecionada = null; ficha.hidden = true; foco = null; enquadrar(); return; }
  if (salas[id]) { focar(id); return; }
  const grupo = id === "times" ? Object.values(salas).filter(s => s.time) : ["qualidade", "compliance", "gerente"].map(k => salas[k]);
  if (!grupo.length) return;
  selecionada = null; ficha.hidden = true;
  mirar(grupo.reduce((s, r) => s + r.cx, 0) / grupo.length, grupo.reduce((s, r) => s + r.cz, 0) / grupo.length, 46);
}

function ajustar() {
  const l = palco.clientWidth, a = palco.clientHeight;
  if (!l || !a) return;
  renderer.setSize(l, a, false); compositor.setSize(l, a);
  camera.aspect = l / a;
  camera.updateProjectionMatrix();
}
// ao mudar o tamanho da janela reenquadra tambem, senao o predio fica cortado numa tela mais estreita
new ResizeObserver(() => { ajustar(); if (mapa && !selecionada) enquadrar(); }).observe(palco);

const raio = new THREE.Raycaster(), ponteiro = new THREE.Vector2();
let apertou = null;
renderer.domElement.addEventListener("pointerdown", e => { apertou = [e.clientX, e.clientY]; foco = null; });
renderer.domElement.addEventListener("pointerup", e => {
  // so conta como clique se o ponteiro quase nao andou; senao foi um arrasto para girar a camera
  if (!apertou || Math.hypot(e.clientX - apertou[0], e.clientY - apertou[1]) > 5) return;
  const r = renderer.domElement.getBoundingClientRect();
  ponteiro.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
  raio.setFromCamera(ponteiro, camera);
  const acerto = raio.intersectObjects(Object.values(salas).map(s => s.alvo))[0];
  if (acerto) focar(acerto.object.userData.sala);
});

// ------------------------------------------------------------------ animacao
const ponto = new THREE.Vector3(), rumo = new THREE.Vector3();
let ultimo = performance.now();
function quadro(t) {
  requestAnimationFrame(quadro);
  if (document.hidden || !predio) { ultimo = t; return; }
  const dt = Math.min(0.05, (t - ultimo) / 1000), s = t / 1000; ultimo = t;
  if (foco) { controles.target.lerp(foco.alvo, 0.07); camera.position.lerp(foco.posicao, 0.07); if (t > foco.ate) foco = null; }
  controles.update();
  for (const p of gente) {
    const vel = ritmo(p.humor);
    if (p.estado === "sentado") {
      // com trabalho na mao: digita no ritmo do humor do time. Sem trabalho: recostado, quase parado.
      const digita = p.ocupado && !calmo;
      p.bracoE.rotation.x = -1.05 + (digita ? Math.sin(s * 9 * vel + p.fase) * 0.09 : 0.3);
      p.bracoD.rotation.x = -1.05 + (digita ? Math.cos(s * 8 * vel + p.fase) * 0.09 : 0.3);
      p.cabeca.rotation.x = (p.humor === "pressao" ? 0.3 : p.humor === "cauteloso" ? 0.16 : 0) + (digita ? Math.sin(s * 1.6 * vel + p.fase) * 0.05 : 0);
      p.cabeca.rotation.y = calmo ? 0 : Math.sin(s * 0.5 + p.fase) * (digita ? 0.2 : 0.45);
      p.corpo.rotation.x = p.ocupado ? 0 : -0.14;
      if (!calmo && (p.relogio -= dt) <= 0) pausa(p);
    } else if (p.estado === "andando") {
      const alvo = p.caminho[0];
      rumo.subVectors(alvo, p.g.position); rumo.y = 0;
      const falta = rumo.length(), passo = (p.fita.visible ? 2.6 : 1.9) * vel * dt;
      if (falta <= passo) { p.g.position.set(alvo.x, 0, alvo.z); p.caminho.shift(); if (!p.caminho.length) { const f = p.aoChegar; p.aoChegar = null; p.estado = "parado"; p.relogio = 0.5; f?.(); } }
      else { p.g.position.addScaledVector(rumo.normalize(), passo); p.g.rotation.y = Math.atan2(rumo.x, rumo.z); }
      const balanco = Math.sin(s * 9 * vel + p.fase) * 0.55;
      p.pernaE.rotation.x = balanco; p.pernaD.rotation.x = -balanco;
      p.bracoE.rotation.x = p.fita.visible ? -1.15 : -balanco * 0.8; p.bracoD.rotation.x = p.fita.visible ? -1.15 : balanco * 0.8;
      p.cabeca.rotation.set(p.humor === "pressao" ? 0.25 : 0, 0, 0); p.corpo.rotation.x = 0;
    } else if (p.estado === "parado") {
      p.pernaE.rotation.x = p.pernaD.rotation.x = 0; p.bracoE.rotation.x = Math.sin(s * 3 + p.fase) * 0.25 - 0.2; p.bracoD.rotation.x = -0.1;
      p.cabeca.rotation.y = Math.sin(s * 1.4 + p.fase) * 0.2;
      // chegou trabalho enquanto estava na pausa: volta na hora
      if (((p.relogio -= dt) <= 0 || (p.ocupado && p.onde !== p.sala)) && !p.entregando) voltar(p);
    } else if (p.estado === "festa") {
      p.g.position.y = Math.abs(Math.sin(s * 9 + p.fase)) * 0.28; p.bracoE.rotation.x = p.bracoD.rotation.x = -2.8 + Math.sin(s * 14) * 0.2;
      if ((p.relogio -= dt) <= 0) { p.g.position.y = 0; voltar(p); }
    }
    if (p.balao) {
      if (t > p.balaoAte) { p.balao.remove(); p.balao = null; }
      else { ponto.set(p.g.position.x, p.g.position.y + 2.15, p.g.position.z).project(camera);
             p.balao.style.left = ((ponto.x + 1) / 2 * palco.clientWidth) + "px"; p.balao.style.top = ((1 - ponto.y) / 2 * palco.clientHeight) + "px"; }
    }
  }
  compositor.render();
}

// ----------------------------------------------------------- demonstracao
function simulador() {
  const nomes = [["kick:norte", "Norte", "animado"], ["twitch:vega", "Vega", "normal"], ["kick:atlas", "Atlas", "cauteloso"],
                 ["twitch:lira", "Lira", "pressao"], ["youtube:orion", "Orion", "animado"], ["kick:duna", "Duna", "normal"]];
  const elenco = "Ariel Bia Caio Dani Edu Fabi Gabi Hugo Iara Joca Kai Lia Malu Nico Olga Pedro Quim Rafa Sol Teo Uli Val Wes Yara".split(" ");
  const humores = { animado: ["animado", 0.9, "ganha 1 vaga a mais na pauta do CEO"], normal: ["normal", 0.55, "regras padrão"],
                    cauteloso: ["cauteloso", 0.3, "o líder exige 1 ponto a mais de nota"], pressao: ["sob pressão", 0.1, "o líder exige 2 pontos a mais e o time perde 1 vaga na pauta"] };
  const papeis = [["radar", "Radar", "acha o momento na live"], ["edicao", "Edição", "corta, enquadra e legenda"],
                  ["redacao", "Redação", "escreve título, gancho e legendas"], ["lider", "Líder do time", "valida a entrega do time"]];
  const gestores = [["qualidade", "Analista de qualidade", "Qualidade"], ["compliance", "Analista de compliance", "Compliance"],
                    ["gerente", "Gerente de conteúdo", "Gerência de conteúdo"], ["diretor", "Diretor editorial", "Diretoria editorial"]];
  const nomeDe = (chave, k) => elenco[(semente(chave) + k * 7) % elenco.length];
  let cortes = [], n = 0, aprovados = 0, eventos = [];
  const fazendo = {}, feitos = Object.fromEntries(nomes.map(([c]) => [c, 0])), bons = { ...feitos };
  const hora = () => { const d = new Date(); return new Date(d - d.getTimezoneOffset() * 60000).toISOString().slice(0, 19); };
  const dizer = (chave, papel, texto) => {
    fazendo[chave + "/" + papel] = texto;
    const time = nomes.find(x => x[0] === chave), k = papeis.findIndex(x => x[0] === papel);
    eventos.push({ quando: hora(), chave, papel, texto, quem: time ? `${nomeDe(chave, k)} · ${papeis[k][1]} · ${time[1]}` : gestores.find(g => g[0] === papel)?.[1] || "CEO" });
    eventos = eventos.slice(-40);
  };
  return () => {
    // a cada leitura: nasce um corte, os outros andam uma etapa, alguns sao barrados e o CEO decide o que chegou nele
    cortes = cortes.filter(c => !c.fim || --c.fim > 0);
    for (const c of cortes) {
      if (c.fim) continue;
      const i = ORDEM.indexOf(c.etapa), [, canal, nivel] = nomes.find(x => x[0] === c.canal_chave), chance = humores[nivel][1];
      if (c.etapa === "ceo") { if (Math.random() < 0.45) { const ok = Math.random() < chance + 0.15; c.etapa = ok ? "aprovado" : "descartado"; c.fim = 2; dizer("empresa", "ceo", `${canal}: ${ok ? "aprovou" : "reprovou"} ${c.nome}`); if (ok) { aprovados++; bons[c.canal_chave]++; } } }
      else if (Math.random() < 0.6) {
        const barrado = Math.random() > 0.72 + chance * 0.25, quem = c.etapa === "lider_time" ? [c.canal_chave, "lider", ""] : ["empresa", c.etapa, canal + ": "];
        dizer(quem[0], quem[1], quem[2] + (barrado ? `barrou ${c.nome}: ${um(["música em destaque", "nota baixa", "título não entrega", "corte curto demais"])}` : `aprovou ${c.nome}`));
        if (barrado) { c.etapa = "descartado"; c.fim = 2; } else c.etapa = ORDEM[i + 1];
      }
    }
    if (Math.random() < 0.75) {
      const [chave] = um(nomes), nome = `${1 + n % 5}h${String(n * 7 % 60).padStart(2, "0")}m`; feitos[chave]++; n++;
      dizer(chave, "radar", `achou 1 momento: ${nome}`); dizer(chave, "redacao", "avaliando 3 candidato(s) e escrevendo titulo e legendas");
      dizer(chave, "edicao", `corte ${nome} pronto, entregue ao lider`);
      cortes.push({ id: "demo/" + n, nome, canal_chave: chave, etapa: "lider_time", titulo: "" });
    }
    for (const chave of Object.keys(fazendo)) if (Math.random() < 0.18) delete fazendo[chave];
    const fila = e => cortes.filter(c => c.etapa === e).length;
    return {
      agora: hora(), empresa: "Agência de Cortes", etapas: [], cortes: cortes.map(c => ({ ...c })), vigia: { rodando: true, desde: hora() }, eventos: [...eventos], ticker: [],
      times: nomes.map(([chave, canal, nivel]) => ({ chave, canal, autorizado: nivel !== "pressao", ligado: true, situacao: "olhando a live",
        humor: { nivel, rotulo: humores[nivel][0], taxa: humores[nivel][1], decisoes: 10, efeito: humores[nivel][2] },
        feitos_hoje: feitos[chave], aprovados_hoje: bons[chave], aprovados_ceo: bons[chave], fila: cortes.filter(c => c.canal_chave === chave && c.etapa === "lider_time").length,
        pessoas: papeis.map(([papel, cargo, faz], k) => ({ id: chave + "/" + papel, papel, cargo, faz, nome: nomeDe(chave, k), fazendo: fazendo[chave + "/" + papel] || "" })),
        feedback: [{ de: "Gerente de conteúdo", texto: "Começar o corte na pergunta, não na resposta" }] })),
      gestao: gestores.map(([id, nome, cargo]) => ({ id, nome, cargo, fila: fila(id), hoje: "simulação", fazendo: fazendo["empresa/" + id] || "" })),
      ceo: { nome: "CEO", fila: fila("ceo"), hoje: "aprovou " + aprovados, fazendo: "" },
    };
  };
}
const simular = DEMO ? simulador() : null;
$("demo").hidden = !DEMO;
async function atualizar() {
  try { aplicar(DEMO ? simular() : await (await fetch("/api/escritorio")).json()); } catch (erro) { console.error(erro); }
}
await atualizar();
requestAnimationFrame(quadro);
setInterval(atualizar, DEMO ? 3500 : 4000);
</script>
</body>
</html>
"""
