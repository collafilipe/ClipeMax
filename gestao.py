"""
Pagina Gestao: o que antes era comando no terminal, agora no site.

    Desempenho   receita estimada por canal (--painel) e avaliacao dos times e da gerencia (--avaliacao)
    Times        opcoes de cada canal do canais.txt (cliente, autorizacao, jogo, cortes por hora, contrato)
    Postagem     contas conectadas, simular, postar os aprovados e trazer as views (--postar, --atualizar-views)
    Empresa      nomes da equipe e regras da esteira (empresa.json)

As funcoes devolvem dicionarios prontos para virar JSON; revisao.py so encaminha as rotas.
"""
import dataclasses
import datetime
import json
import threading

import agencia
import esteira
import postagem
from fontes import RAIZ

PASTAS = {"pendente": RAIZ / "prontos", "aprovado": RAIZ / "aprovados", "descartado": RAIZ / "descartados"}
CARTEIRA, EMPRESA, SEGREDOS = RAIZ / "canais.txt", RAIZ / "empresa.json", RAIZ / "segredos"
# ultimo recado de cada tentativa de conectar conta: a autorizacao acontece no navegador, fora deste pedido
_CONEXAO = {}


def _carteira():
    return agencia.ler_carteira(CARTEIRA) if CARTEIRA.exists() else []


def painel(consulta):
    """Receita por canal e avaliacao da equipe. ?dias=30 limita o periodo da receita (0 = tudo)."""
    dias = int((consulta.get("dias") or ["30"])[0])
    carteira, cortes = _carteira(), agencia.ler_cortes(PASTAS)
    desde = datetime.datetime.now() - datetime.timedelta(days=dias) if dias else None
    receita = agencia.resumo_por_canal(carteira, cortes, desde)
    for linha in receita:
        linha["ultimo"] = linha["ultimo"].isoformat(timespec="minutes") if linha["ultimo"] else None
    times, gerente = esteira.avaliacao(cortes, carteira)
    return {"dias": dias, "receita": receita, "times": times, "gerente": gerente}


def _contas(plataforma):
    """Contas ja conectadas: cada arquivo de token em segredos/ e uma conta."""
    prefixo = f"{plataforma}_token"
    nomes = [a.stem[len(prefixo):].lstrip("_") or "principal" for a in SEGREDOS.glob(f"{prefixo}*.json")] if SEGREDOS.exists() else []
    return sorted(nomes)


def config(consulta=None):
    try:
        propria = json.loads(EMPRESA.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        propria = {}
    cortes = agencia.ler_cortes(PASTAS)
    return {
        "empresa": {**esteira.EMPRESA_PADRAO, **{k: v for k, v in propria.items() if k in esteira.EMPRESA_PADRAO}},
        "times": [{**dataclasses.asdict(c), "chave": c.chave, "nome": c.nome} for c in _carteira()],
        "postagem": {p: {"app": (SEGREDOS / f"{p}_app.json").exists(), "contas": _contas(p), "recado": _CONEXAO.get(p, ""),
                         "esperando": sum(1 for c in cortes if c["situacao"] == "aprovado" and not c.get(f"postado_{p}"))}
                     for p in postagem.PLATAFORMAS},
    }


def salvar_empresa(dados):
    """Grava em empresa.json so o que difere do padrao. Recusa opcao desconhecida e numero fora da faixa."""
    campos = dados.get("campos") or {}
    try:
        propria = json.loads(EMPRESA.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        propria = {}
    for nome, valor in campos.items():
        if nome not in esteira.EMPRESA_PADRAO:
            raise ValueError(f"opcao desconhecida: {nome}")
        padrao = esteira.EMPRESA_PADRAO[nome]
        if isinstance(padrao, int):
            try:
                valor = int(valor)
            except (TypeError, ValueError):
                raise ValueError(f"{nome} precisa ser um numero inteiro") from None
            limite = 10 if nome.startswith("nota_") else 600 if nome.startswith("duracao_") else 50
            if not 1 <= valor <= limite:
                raise ValueError(f"{nome} precisa ficar entre 1 e {limite}")
        else:
            valor = str(valor).strip()[:200]
            if nome != "opcoes_da_vigia" and not valor:
                valor = padrao  # nome em branco volta ao padrao
        if valor == padrao:
            propria.pop(nome, None)
        else:
            propria[nome] = valor
    final = {**esteira.EMPRESA_PADRAO, **propria}
    if final["duracao_minima"] >= final["duracao_maxima"]:
        raise ValueError("a duracao minima precisa ser menor que a maxima")
    EMPRESA.write_text(json.dumps(propria, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"mensagem": "Empresa salva. Vale a partir da próxima rodada da esteira."}


def salvar_time(dados):
    chave = str(dados.get("chave", ""))
    if dados.get("remover"):
        agencia.remover_canal(CARTEIRA, chave)
        return {"mensagem": f"Time {chave} removido. Os cortes já feitos continuam nas pastas."}
    canal = agencia.atualizar_canal(CARTEIRA, chave, dados.get("campos") or {})
    return {"mensagem": f"Time {canal.nome} salvo. Vale a partir da próxima rodada da vigia."}


def postar(dados):
    """Simula ou posta os aprovados. So entra corte aprovado, de canal autorizado e ainda nao postado (veja postagem.py)."""
    plataforma, visibilidade = str(dados.get("plataforma", "")), str(dados.get("visibilidade", "privado"))
    if plataforma not in postagem.PLATAFORMAS or visibilidade not in postagem.VISIBILIDADES:
        raise ValueError("plataforma ou visibilidade invalida")
    linhas = []
    feitos = postagem.postar(agencia.ler_cortes(PASTAS), _carteira(), plataforma, SEGREDOS, visibilidade,
                             max(0, int(dados.get("limite") or 0)), bool(dados.get("simular", True)), log=linhas.append)
    return {"feitos": feitos, "linhas": [str(l).strip() for l in linhas]}


def views(dados):
    linhas = []
    total = postagem.atualizar_views(agencia.ler_cortes(PASTAS), _carteira(), SEGREDOS, log=linhas.append)
    return {"feitos": total, "linhas": [str(l).strip() for l in linhas]}


def conectar(dados):
    """Abre o navegador para o dono autorizar a conta. O login e sempre dele; aqui so disparamos e guardamos o recado."""
    plataforma = str(dados.get("plataforma", ""))
    conta = agencia._conta(str(dados.get("conta") or "principal"), 0)
    if plataforma not in postagem.PLATAFORMAS:
        raise ValueError("plataforma invalida")
    try:
        postagem.ler_app(SEGREDOS, plataforma)  # sem as chaves do app nem adianta abrir o navegador
    except postagem.ErroDePostagem as err:
        raise ValueError(str(err)) from None

    def trabalho():
        try:
            postagem.conectar(SEGREDOS, plataforma, conta, log=lambda m: None)
            _CONEXAO[plataforma] = f"Conta {conta} conectada."
        except Exception as err:  # o recado e o unico jeito de o erro chegar a tela
            _CONEXAO[plataforma] = f"Não conectou: {err}"

    _CONEXAO[plataforma] = "Autorize no navegador que acabou de abrir."
    threading.Thread(target=trabalho, daemon=True).start()
    return {"mensagem": _CONEXAO[plataforma]}


CONSULTAS = {"/api/painel": painel, "/api/config": config}
ACOES = {"/api/config/empresa": salvar_empresa, "/api/config/time": salvar_time, "/api/postar": postar,
         "/api/views": views, "/api/conectar": conectar}


PAGINA = r"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Gestão</title>
<style>
  :root {
    --fundo: #070a11; --painel: #0e131d; --painel2: #141b28; --borda: #26303f; --texto: #f1ece0; --fraco: #9aa3b2;
    --latao: #d4af5a; --latao2: #8f7434; --alta: #3ddc84; --baixa: #ff5d5d; --ambar: #f0a63a; --campo: #080b12;
    --serifa: "Playfair Display", "Bodoni MT", Didot, Georgia, "Times New Roman", serif;
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--fundo); color: var(--texto); font: 15px/1.5 system-ui, "Segoe UI", sans-serif; }
  header { display: flex; align-items: center; gap: 10px 22px; padding: 10px 20px; flex-wrap: wrap; position: sticky; top: 0; z-index: 5;
           background: linear-gradient(#0f1522, #0a0e17); border-bottom: 1px solid var(--latao2); }
  .marca { font-family: var(--serifa); font-size: 19px; letter-spacing: .14em; text-transform: uppercase; color: var(--latao); margin: 0; font-weight: 700; }
  nav { display: flex; gap: 4px; flex-wrap: wrap; }
  nav a { color: var(--fraco); text-decoration: none; padding: 6px 12px; border-radius: 6px; font-size: 13px; letter-spacing: .04em; text-transform: uppercase; }
  nav a:hover { color: var(--texto); }
  nav a[aria-current] { color: var(--latao); background: #1a2231; }
  main { padding: 20px 20px 60px; max-width: 1240px; margin: 0 auto; display: grid; gap: 18px; }
  .abas { display: flex; gap: 6px; flex-wrap: wrap; }
  .abas button { background: transparent; color: var(--fraco); border: 1px solid var(--borda); border-radius: 999px; padding: 6px 16px; font: inherit; cursor: pointer; }
  .abas button[aria-pressed="true"] { background: var(--latao); color: #1a1206; border-color: var(--latao); font-weight: 600; }
  section[hidden] { display: none; }
  section { display: grid; gap: 16px; }
  h2 { font: 700 22px/1.2 var(--serifa); color: var(--latao); margin: 6px 0 0; }
  .sub { color: var(--fraco); font-size: 13px; margin: -10px 0 0; }
  .cartao { background: var(--painel); border: 1px solid var(--borda); border-radius: 12px; padding: 16px; display: grid; gap: 12px; }
  .cartao h3 { margin: 0; font: 700 17px/1.2 var(--serifa); }
  .rolagem { overflow-x: auto; }
  table { border-collapse: collapse; width: 100%; font-size: 14px; }
  th { text-align: right; color: var(--fraco); font-weight: 600; font-size: 11px; letter-spacing: .08em; text-transform: uppercase; padding: 6px 10px; white-space: nowrap; }
  td { text-align: right; padding: 8px 10px; border-top: 1px solid var(--borda); font-variant-numeric: tabular-nums; white-space: nowrap; }
  th:first-child, td:first-child { text-align: left; }
  td.aviso { color: var(--ambar); font-size: 12px; text-align: left; }
  .grade { display: grid; gap: 10px 14px; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); }
  label { display: grid; gap: 4px; font-size: 12px; color: var(--fraco); }
  label.marcar { display: flex; align-items: center; gap: 8px; color: var(--texto); font-size: 14px; }
  input[type=text], input[type=number], select { width: 100%; background: var(--campo); color: var(--texto); border: 1px solid var(--borda);
       border-radius: 8px; padding: 8px 10px; font: inherit; font-size: 14px; min-width: 0; }
  input[type=checkbox] { width: 18px; height: 18px; accent-color: var(--latao); }
  .acoes { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
  button.acao, button.leve, button.perigo { border-radius: 8px; padding: 9px 16px; font: inherit; cursor: pointer; }
  button.acao { border: 0; font-weight: 700; background: var(--latao); color: #1a1206; }
  button.leve { background: none; border: 1px solid var(--borda); color: var(--texto); }
  button.leve:hover { border-color: var(--fraco); }
  button.perigo { background: none; border: 1px solid color-mix(in srgb, var(--baixa) 55%, transparent); color: var(--baixa); }
  button:disabled { opacity: .55; cursor: progress; }
  .recado { margin: 0; font-size: 13px; color: var(--fraco); }
  .recado.erro { color: var(--baixa); } .recado.ok { color: var(--alta); }
  pre { margin: 0; background: var(--campo); border: 1px solid var(--borda); border-radius: 8px; padding: 10px 12px; font: 13px/1.5 ui-monospace, Consolas, monospace;
        white-space: pre-wrap; overflow-wrap: anywhere; color: var(--texto); max-height: 260px; overflow-y: auto; }
  pre:empty { display: none; }
  .selo { display: inline-block; border-radius: 999px; padding: 1px 10px; font-size: 12px; font-weight: 700; background: var(--borda); color: var(--fraco); }
  .selo.ok { background: var(--alta); color: #06140c; } .selo.falta { background: var(--ambar); color: #1a1206; }
  .vazio { color: var(--fraco); margin: 0; }
  a { color: var(--latao); }
  :focus-visible { outline: 2px solid var(--latao); outline-offset: 2px; }
  @media (max-width: 520px) { main { padding: 16px 16px 48px; } }
</style>
</head>
<body>
<header>
  <p class="marca" id="marca">ClipeMax</p>
  <nav>
    <a href="/escritorio">Escritório</a>
    <a href="/">Aprovação</a>
    <a href="/escritorio/mesas">Lista</a>
    <a href="/gestao" aria-current="page">Gestão</a>
  </nav>
</header>
<main>
  <div class="abas" id="abas"></div>

  <section id="desempenho">
    <h2>Desempenho</h2>
    <p class="sub">Receita estimada pelo contrato de cada canal e a equipe medida pelas suas decisões.</p>
    <div class="cartao">
      <div class="acoes"><h3>Receita por canal</h3>
        <select id="dias" aria-label="Período" style="width:auto;margin-left:auto">
          <option value="7">Últimos 7 dias</option><option value="30" selected>Últimos 30 dias</option>
          <option value="90">Últimos 90 dias</option><option value="0">Todo o histórico</option></select></div>
      <div class="rolagem"><table id="receita"></table></div>
      <p class="recado">Receita estimada = mensalidade + views × valor por mil views. É estimativa do contrato, não extrato.</p>
    </div>
    <div class="cartao"><h3>Equipe</h3><div class="rolagem"><table id="equipe"></table></div><p class="recado" id="gerente"></p></div>
  </section>

  <section id="times" hidden>
    <h2>Times</h2>
    <p class="sub">Um time por canal. As mudanças valem a partir da próxima rodada da vigia; não precisa reiniciar.</p>
    <form class="cartao" id="novoTime">
      <h3>Novo time</h3>
      <div class="acoes"><input type="text" id="novoCanal" placeholder="Link do canal (Twitch, Kick ou YouTube)" aria-label="Link do canal" style="flex:1;min-width:220px" required>
        <button class="acao" type="submit">Criar time</button></div>
      <p class="recado" id="recadoNovo" role="status"></p>
    </form>
    <div id="listaTimes" style="display:grid;gap:16px"></div>
  </section>

  <section id="postagem" hidden>
    <h2>Postagem</h2>
    <p class="sub">Só entra corte que você aprovou, de canal com autorização, e que ainda não foi postado naquela plataforma.</p>
    <div id="plataformas" style="display:grid;gap:16px"></div>
  </section>

  <section id="empresa" hidden>
    <h2>Empresa</h2>
    <p class="sub">Nomes que aparecem nas telas e as regras da cadeia de aprovação.</p>
    <form class="cartao" id="formEmpresa"><div class="grade" id="camposEmpresa"></div>
      <div class="acoes"><button class="acao" type="submit">Salvar</button><p class="recado" id="recadoEmpresa" role="status"></p></div></form>
  </section>
</main>
<script>
const $ = id => document.getElementById(id);
const el = (tag, props = {}, filhos = []) => { const n = Object.assign(document.createElement(tag), props); filhos.forEach(f => n.append(f)); return n; };
const reais = v => "R$ " + v.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const pct = v => v === null || v === undefined ? "–" : Math.round(v * 100) + "%";
async function pedir(caminho, corpo) {
  const r = await fetch(caminho, corpo ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo) } : {});
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.erro || "erro " + r.status);
  return j;
}
function recado(no, texto, tipo = "") { no.textContent = texto; no.className = "recado " + tipo; }
// roda uma acao de botao: trava o botao enquanto espera e mostra o resultado ou o erro no recado ao lado
async function comBotao(botao, no, fazer) {
  botao.disabled = true; recado(no, "Aguarde…");
  try { recado(no, await fazer() || "", "ok"); } catch (e) { recado(no, "Não deu: " + e.message, "erro"); }
  botao.disabled = false;
}

const ABAS = { desempenho: "Desempenho", times: "Times", postagem: "Postagem", empresa: "Empresa" };
function abrir(aba) {
  for (const id of Object.keys(ABAS)) $(id).hidden = id !== aba;
  $("abas").replaceChildren(...Object.entries(ABAS).map(([id, nome]) => {
    const b = el("button", { type: "button", textContent: nome, onclick: () => { location.hash = id; abrir(id); } });
    b.setAttribute("aria-pressed", String(id === aba)); return b; }));
  if (aba === "desempenho") desempenho(); else configuracoes();
}

// ---------------------------------------------------------------- desempenho
function tabela(no, cabecalho, linhas, vazio) {
  if (!linhas.length) { no.replaceChildren(el("caption", { className: "vazio", textContent: vazio })); return; }
  no.replaceChildren(el("thead", {}, [el("tr", {}, cabecalho.map(c => el("th", { textContent: c })))]),
                     el("tbody", {}, linhas.map(l => el("tr", {}, l.map(c => c instanceof Node ? c : el("td", { textContent: String(c) }))))));
}
async function desempenho() {
  let q; try { q = await pedir("/api/painel?dias=" + $("dias").value); } catch { return; }
  tabela($("receita"), ["Canal", "Pendentes", "Aprovados", "Descartados", "Aprovação", "Views", "Receita est.", "Último corte", ""],
    q.receita.map(l => [l.canal, l.pendentes, l.aprovados, l.descartados, pct(l.aprovacao), l.views.toLocaleString("pt-BR"), reais(l.receita),
                        l.ultimo ? l.ultimo.replace("T", " ").slice(5) : "nunca", el("td", { className: "aviso", textContent: l.autorizado ? "" : "sem autorização" })]),
    "Nenhum canal ainda. Crie um time na aba Times.");
  tabela($("equipe"), ["Time", "Feitos", "Líder barrou", "Qualidade", "Compliance", "Gerência", "Você aprovou", "Você reprovou", "Aprovação", "Humor"],
    q.times.map(l => [l.time, l.produzidos, l.barrados_lider_time, l.barrados_qualidade, l.barrados_compliance, l.barrados_gerente, l.aprovados_ceo, l.reprovados_ceo, pct(l.aprovacao_ceo), l.humor]),
    "Nenhum corte produzido ainda.");
  const g = q.gerente;
  $("gerente").textContent = `Gerência: de ${g.julgados_pelo_ceo} corte(s) que ela aprovou e você já decidiu, você aprovou ${pct(g.acerto)}. Barrados por ela que você resgatou: ${g.barrados_que_o_ceo_resgatou}.`
    + (g.julgados_pelo_ceo < 20 ? " Com menos de 20 decisões suas, estes percentuais ainda não dizem muita coisa." : "");
}
$("dias").onchange = desempenho;

// ---------------------------------------------------------- times e empresa
const CAMPOS_DO_TIME = [["cliente", "Nome do cliente", "text"], ["funcionario", "Nome do líder do time", "text"], ["jogo", "Só cortar este jogo (vazio = qualquer)", "text"],
  ["tags", "Hashtags fixas", "text"], ["idioma", "Idioma da fala (pt, en...; vazio = detectar)", "text"], ["por_hora", "Cortes por hora de live (padrão 3)", "number"], ["cortes", "Cortes na primeira leitura (padrão 8)", "number"],
  ["prioridade", "Prioridade (1 passa na frente, 9 por último)", "number"], ["conta", "Conta de postagem", "text"],
  ["mensalidade", "Mensalidade do contrato (R$)", "number"], ["valor_mil_views", "Valor por mil views (R$)", "number"]];
function cartaoDoTime(t) {
  const entradas = {}, no = el("p", { className: "recado" }); no.setAttribute("role", "status");
  const grade = el("div", { className: "grade" }, CAMPOS_DO_TIME.map(([campo, rotulo, tipo]) => {
    const e = el("input", { type: tipo, value: t[campo] ?? "" }); if (tipo === "number") { e.min = 0; e.step = "any"; }
    entradas[campo] = e; return el("label", {}, [document.createTextNode(rotulo), e]); }));
  const marcar = (campo, rotulo) => { const e = el("input", { type: "checkbox", checked: t[campo] }); entradas[campo] = e; return el("label", { className: "marcar" }, [e, document.createTextNode(rotulo)]); };
  const salvar = el("button", { type: "button", className: "acao", textContent: "Salvar" });
  salvar.onclick = () => comBotao(salvar, no, async () => (await pedir("/api/config/time", { chave: t.chave,
    campos: Object.fromEntries(Object.entries(entradas).map(([k, e]) => [k, e.type === "checkbox" ? e.checked : e.value])) })).mensagem);
  const remover = el("button", { type: "button", className: "perigo", textContent: "Remover time" });
  remover.onclick = () => { if (!confirm(`Remover o time ${t.nome}? Os cortes já feitos continuam nas pastas.`)) return;
    comBotao(remover, no, async () => { const r = await pedir("/api/config/time", { chave: t.chave, remover: true }); configuracoes(); return r.mensagem; }); };
  return el("div", { className: "cartao" }, [el("div", { className: "acoes" }, [el("h3", { textContent: t.nome }), el("span", { className: "recado", textContent: t.url })]), grade,
    el("div", { className: "acoes" }, [marcar("autorizado", "O streamer autorizou os cortes (libera a postagem)"), marcar("vigiar", "Acompanhar o canal sozinho (desmarcado: só os links que você passar)")]),
    el("div", { className: "acoes" }, [salvar, remover, no])]);
}
const CAMPOS_DA_EMPRESA = [["nome", "Nome da empresa", "text"], ["ceo", "Como você aparece", "text"], ["diretor", "Nome do diretor editorial", "text"], ["gerente", "Nome do gerente de conteúdo", "text"],
  ["compliance", "Nome do analista de compliance", "text"], ["qualidade", "Nome do analista de qualidade", "text"],
  ["cota_ceo_por_canal", "Cortes por canal que chegam a você por dia", "number"], ["nota_minima_time", "Nota mínima do time (0 a 10)", "number"],
  ["nota_minima_gerente", "Nota mínima da gerência (0 a 10)", "number"], ["duracao_minima", "Duração mínima do corte (s)", "number"], ["duracao_maxima", "Duração máxima do corte (s)", "number"],
  ["opcoes_da_vigia", "Opções extras da vigia (avançado), ex: --jogo \"gta 6\"", "text"]];
const entradasDaEmpresa = {};
function cartaoDaPlataforma(nome, p) {
  const titulo = { youtube: "YouTube Shorts", tiktok: "TikTok (rascunho)" }[nome], saida = el("pre"), no = el("p", { className: "recado", textContent: p.recado }); no.setAttribute("role", "status");
  const conta = el("input", { type: "text", value: "principal", style: "width:150px" }); conta.setAttribute("aria-label", "Nome da conta");
  const conectar = el("button", { type: "button", className: "leve", textContent: "Conectar conta" });
  conectar.onclick = () => comBotao(conectar, no, async () => (await pedir("/api/conectar", { plataforma: nome, conta: conta.value })).mensagem);
  const visibilidade = el("select", { style: "width:auto" }, [["privado", "Privado (para conferir)"], ["nao_listado", "Não listado"], ["publico", "Público"]].map(([v, r]) => el("option", { value: v, textContent: r })));
  visibilidade.setAttribute("aria-label", "Visibilidade"); visibilidade.hidden = nome !== "youtube";
  const rodar = (botao, simular) => comBotao(botao, no, async () => {
    const r = await pedir("/api/postar", { plataforma: nome, visibilidade: visibilidade.value, simular }); saida.textContent = r.linhas.join("\n");
    if (!simular) configuracoes(); return simular ? "Simulação: nada foi enviado." : r.feitos + " corte(s) postado(s)."; });
  const simular = el("button", { type: "button", className: "leve", textContent: "Ver o que seria postado" }); simular.onclick = () => rodar(simular, true);
  const postar = el("button", { type: "button", className: "acao", textContent: "Postar os aprovados" });
  postar.onclick = () => { if (confirm(`Postar agora no ${titulo}? Isso envia os vídeos para a sua conta.`)) rodar(postar, false); };
  const linhas = [el("div", { className: "acoes" }, [el("h3", { textContent: titulo }), el("span", { className: "selo " + (p.app ? "ok" : "falta"), textContent: p.app ? "app configurado" : "falta o arquivo do app" }),
    el("span", { className: "selo " + (p.contas.length ? "ok" : "falta"), textContent: p.contas.length ? "contas: " + p.contas.join(", ") : "nenhuma conta conectada" }),
    el("span", { className: "selo", textContent: p.esperando + " aprovado(s) sem postar" })])];
  if (!p.app) linhas.push(el("p", { className: "recado", textContent: `Para ligar: salve as chaves do app em segredos\\${nome}_app.json (passo a passo no README, seção Postagem) e conecte a conta aqui.` }));
  linhas.push(el("div", { className: "acoes" }, [conta, conectar]), el("div", { className: "acoes" }, [visibilidade, simular, postar]));
  if (nome === "youtube") {
    const views = el("button", { type: "button", className: "leve", textContent: "Atualizar views dos Shorts" });
    views.onclick = () => comBotao(views, no, async () => { const r = await pedir("/api/views", {}); saida.textContent = r.linhas.join("\n"); return r.feitos + " corte(s) atualizado(s)."; });
    linhas.push(el("div", { className: "acoes" }, [views]));
  } else linhas.push(el("p", { className: "recado", textContent: "O vídeo vai para a caixa de entrada da conta; a legenda é colada e a publicação é feita no aplicativo. Limite da API: 5 rascunhos pendentes por dia." }));
  linhas.push(no, saida);
  return el("div", { className: "cartao" }, linhas);
}
async function configuracoes() {
  let q; try { q = await pedir("/api/config"); } catch { return; }
  $("marca").textContent = q.empresa.nome; document.title = "Gestão · " + q.empresa.nome;
  $("listaTimes").replaceChildren(...(q.times.length ? q.times.map(cartaoDoTime) : [el("p", { className: "vazio", textContent: "Nenhum time ainda." })]));
  $("plataformas").replaceChildren(...Object.entries(q.postagem).map(([n, p]) => cartaoDaPlataforma(n, p)));
  $("camposEmpresa").replaceChildren(...CAMPOS_DA_EMPRESA.map(([campo, rotulo, tipo]) => {
    const e = el("input", { type: tipo, value: q.empresa[campo] ?? "" }); entradasDaEmpresa[campo] = e; return el("label", {}, [document.createTextNode(rotulo), e]); }));
}
$("formEmpresa").addEventListener("submit", ev => { ev.preventDefault();
  comBotao(ev.submitter, $("recadoEmpresa"), async () => { const r = await pedir("/api/config/empresa", { campos: Object.fromEntries(Object.entries(entradasDaEmpresa).map(([k, e]) => [k, e.value])) }); configuracoes(); return r.mensagem; }); });
$("novoTime").addEventListener("submit", ev => { ev.preventDefault();
  comBotao(ev.submitter, $("recadoNovo"), async () => { const r = await pedir("/api/pedido", { url: $("novoCanal").value }); $("novoCanal").value = ""; configuracoes(); return r.mensagem; }); });

const daBarra = () => abrir(ABAS[location.hash.slice(1)] ? location.hash.slice(1) : "desempenho");
// link direto para uma aba (/gestao#postagem) tambem funciona com a pagina ja aberta
addEventListener("hashchange", daBarra);
daBarra();
</script>
</body>
</html>
"""
