"""Tela de revisao: lista os cortes, toca o video, copia titulo/hashtags e aprova ou descarta."""
import json
import mimetypes
import os
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

import agencia
import escritorio3d
import esteira
import expediente
import gestao
import pedidos
from fontes import RAIZ, log

PASTAS = {"pendente": RAIZ / "prontos", "aprovado": RAIZ / "aprovados", "descartado": RAIZ / "descartados"}
DESTINO = {"aprovar": "aprovado", "descartar": "descartado", "restaurar": "pendente"}


def _listar():
    itens = []
    for estado, base in PASTAS.items():
        if not base.exists():
            continue
        for mp4 in sorted(base.rglob("*.mp4"), key=lambda f: f.stat().st_mtime, reverse=True):
            dados = {}
            lado = mp4.with_suffix(".json")
            if lado.exists():
                try:
                    dados = json.loads(lado.read_text(encoding="utf-8"))
                except ValueError:
                    dados = {}
            rel = mp4.relative_to(base).as_posix()
            itens.append({
                "id": f"{estado}/{rel}", "estado": estado, "arquivo": mp4.name, "pasta": mp4.parent.name,
                "caminho": str(mp4), "mb": round(mp4.stat().st_size / 1e6, 1),
                "canal": dados.get("canal") or mp4.parent.name.rsplit("_", 1)[0],
                "titulo": dados.get("titulo", ""), "gancho": dados.get("gancho", ""),
                "tiktok": dados.get("tiktok", ""), "shorts": dados.get("shorts", ""),
                "nota_ia": dados.get("nota_ia"), "motivo": dados.get("motivo", ""),
                "sinais": dados.get("sinais", ""), "trecho": dados.get("trecho", ""),
                "duracao": dados.get("duracao"), "enquadramento": dados.get("enquadramento", ""),
                "fala": dados.get("fala", ""), "origem": dados.get("origem", ""),
                "jogo": dados.get("jogo", ""), "contexto": dados.get("contexto", ""),
                "comentario": dados.get("comentario", ""), "cutscene": bool(dados.get("cutscene")),
                "ofensas": int(dados.get("ofensas") or 0),
                "musica": dados.get("musica", ""), "musica_pct": dados.get("musica_pct"),
                "versao": int(mp4.stat().st_mtime),
                "views_tiktok": dados.get("views_tiktok"), "views_shorts": dados.get("views_shorts"),
                # fila: em qual aba o corte aparece. Pendente so chega ao CEO depois de passar pela esteira.
                "fila": ("ceo" if esteira.etapa_de(dados) == "ceo" else "analise") if estado == "pendente" else estado,
                "etapa": esteira.etapa_de(dados), "trilha": dados.get("trilha", []),
                "nota_gestor": dados.get("nota_gestor"), "antes_do_gestor": dados.get("antes_do_gestor", {}),
                "postado_youtube": (dados.get("postado_youtube") or {}).get("url", ""),
                "postado_tiktok": bool(dados.get("postado_tiktok")),
            })
    return itens


def _resolver(ident):
    """'estado/sub/arquivo.mp4' -> (estado, base, caminho), recusando qualquer coisa fora das pastas de cortes."""
    estado, _, rel = ident.partition("/")
    base = PASTAS.get(estado)
    if not base or not rel:
        return None
    alvo = (base / rel).resolve()
    if base.resolve() not in alvo.parents or alvo.suffix.lower() != ".mp4" or not alvo.exists():
        return None
    return estado, base.resolve(), alvo


def _mover(ident, acao, campos):
    """Grava titulo e legendas editados e, se a acao pedir, move o corte de pasta."""
    achado = _resolver(ident)
    if not achado or (acao not in ("salvar", "puxar") and acao not in DESTINO):
        return False
    estado, base, mp4 = achado
    novo_estado = estado if acao in ("salvar", "puxar") else DESTINO[acao]
    lado = mp4.with_suffix(".json")
    texto = {k: str(v) for k, v in (campos or {}).items() if k in ("titulo", "tiktok", "shorts")}
    for k in ("views_tiktok", "views_shorts"):  # desempenho anotado depois de postar
        if k in (campos or {}):
            try:
                texto[k] = max(0, int(str(campos[k]).replace(".", "").replace(",", "").strip() or 0))
            except ValueError:
                pass
    if texto:
        dados = {}
        if lado.exists():
            try:
                dados = json.loads(lado.read_text(encoding="utf-8"))
            except ValueError:
                dados = {}
        dados.update(texto)
        lado.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    if acao != "salvar":
        # a decisao do CEO entra na trilha antes de mover: e ela que mede se revisor e gestor estao acertando
        try:
            dados = json.loads(lado.read_text(encoding="utf-8")) if lado.exists() else {}
        except ValueError:
            dados = {}
        lado.write_text(json.dumps(esteira.decisao_do_ceo(dados, acao), ensure_ascii=False, indent=1), encoding="utf-8")
        verbo = {"aprovar": "aprovou", "descartar": "reprovou", "restaurar": "resgatou", "puxar": "puxou para a mesa"}[acao]
        esteira.registrar_evento(RAIZ / "estado", "empresa", "ceo", f"{dados.get('canal') or mp4.parent.name}: {verbo} {mp4.stem}")
    if novo_estado == estado:
        return True
    destino = PASTAS[novo_estado] / mp4.relative_to(base.resolve()).parent
    destino.mkdir(parents=True, exist_ok=True)
    # os.replace nao copia: ou move de vez ou falha sem deixar o corte em duas pastas.
    # O video vai primeiro porque e o unico que pode estar aberto pelo player.
    movidos = []
    try:
        for f in (mp4, lado, mp4.with_suffix(".txt"), mp4.with_suffix(".base")):
            if f.exists():
                os.replace(f, destino / f.name)
                movidos.append(f)
    except OSError:
        for f in movidos:  # desfaz o que ja foi
            try:
                os.replace(destino / f.name, f)
            except OSError:
                pass
        return False
    return True


def _comentar(ident, texto):
    """
    Queima o comentario do dono do canal no video. O video sem comentario fica guardado ao lado
    (mesmo nome, extensao .base), entao da para trocar ou tirar o comentario quantas vezes quiser.
    """
    import video
    achado = _resolver(ident)
    if not achado:
        return False, "corte nao encontrado"
    _, _, mp4 = achado
    lado, base, novo = mp4.with_suffix(".json"), mp4.with_suffix(".base"), mp4.with_suffix(".novo")
    dados = {}
    if lado.exists():
        try:
            dados = json.loads(lado.read_text(encoding="utf-8"))
        except ValueError:
            dados = {}
    texto = " ".join(str(texto).split())[:160]
    try:
        if not texto:
            if base.exists():
                os.replace(base, mp4)  # volta ao video sem comentario
        else:
            origem = base if base.exists() else mp4
            # se o corte tem gancho, o comentario entra quando o gancho sai (4 s)
            ok, erro = video.queimar_comentario(origem, novo, texto, 4.2 if dados.get("gancho") else 0.0)
            if not ok:
                return False, erro.strip()[-160:] or "falha ao renderizar"
            if not base.exists():
                os.replace(mp4, base)
            os.replace(novo, mp4)
    except OSError as e:
        novo.unlink(missing_ok=True)
        return False, f"arquivo em uso: {e}"
    dados["comentario"] = texto
    lado.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    return True, ""


def _escritorio():
    try:
        carteira = agencia.ler_carteira(RAIZ / "canais.txt")
    except (OSError, agencia.ErroDeCarteira):
        carteira = []
    try:
        atividade = json.loads((RAIZ / "estado" / "atividade.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        atividade = {}
    try:
        empresa = esteira.carregar_empresa(RAIZ / "empresa.json")
    except ValueError:
        empresa = dict(esteira.EMPRESA_PADRAO)
    quadro = esteira.quadro_do_escritorio(agencia.ler_cortes(PASTAS), carteira, empresa, atividade,
                                          eventos=esteira.ler_eventos(RAIZ / "estado"), vigia=expediente.situacao(RAIZ))
    quadro["pedidos"] = pedidos.listar(RAIZ / "estado", 6)
    return quadro


def _opcoes_da_vigia():
    try:
        return esteira.carregar_empresa(RAIZ / "empresa.json")["opcoes_da_vigia"]
    except ValueError:
        return ""


def _pedido(url, time, cortes, jogo=""):
    """
    O CEO passou um link. Canal: o time passa a acompanhar. Video: entra na fila e e cortado uma vez,
    pela vigia se o expediente estiver aberto, ou por um atendente avulso iniciado aqui.
    """
    link, estado = pedidos.entender_link(url), RAIZ / "estado"
    if link["tipo"] == "canal":
        canal = agencia.adicionar_canal(RAIZ / "canais.txt", link["url"])
        esteira.registrar_evento(estado, "empresa", "ceo", f"montou um time para acompanhar o canal {canal.nome}")
        aberto = expediente.situacao(RAIZ)["rodando"]
        return {"tipo": "canal", "mensagem": f"Time criado para {canal.nome}. " + (
            "Ele entra na próxima rodada da vigia." if aberto else "Abra o expediente para ele começar a acompanhar.")}
    pedido = pedidos.adicionar(estado, link["url"], time, cortes, jogo=jogo)
    esteira.registrar_evento(estado, "empresa", "ceo", f"passou uma live para cortar: {pedido['url']}")
    if not expediente.situacao(RAIZ)["rodando"]:
        expediente.abrir(RAIZ, _opcoes_da_vigia(), nome="avulso")
    return {"tipo": "video", "mensagem": "Live na fila. O time começa em instantes.", "pedido": pedido}


def _expediente(acao):
    """Abre ou fecha a vigia das lives a pedido do CEO, pela tela do escritorio."""
    if acao == "abrir":
        try:
            opcoes = esteira.carregar_empresa(RAIZ / "empresa.json")["opcoes_da_vigia"]
        except ValueError:
            opcoes = ""
        agencia.ler_carteira(RAIZ / "canais.txt")  # carteira invalida: melhor avisar aqui do que a vigia morrer calada
        estado = expediente.abrir(RAIZ, opcoes)
        esteira.registrar_evento(RAIZ / "estado", "empresa", "ceo", "abriu o expediente: os times estao acompanhando as lives")
        return estado
    if acao == "fechar":
        estado = expediente.fechar(RAIZ)
        esteira.registrar_evento(RAIZ / "estado", "empresa", "ceo", "fechou o expediente")
        return estado
    raise ValueError("acao desconhecida")


class Tela(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _local(self):
        """So atende o proprio navegador nesta maquina: recusa pedidos vindos de outros sites ou outros nomes."""
        porta = self.server.server_address[1]
        if self.headers.get("Host", "") not in (f"127.0.0.1:{porta}", f"localhost:{porta}"):
            return False
        origem = self.headers.get("Origin")
        return origem in (None, f"http://127.0.0.1:{porta}", f"http://localhost:{porta}")

    def _json(self, obj, status=200):
        corpo = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self):
        if not self._local():
            self.send_error(403)
            return
        caminho = unquote(self.path.split("?")[0])
        if caminho == "/":
            corpo = PAGINA.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)
        elif caminho == "/api/cortes":
            self._json(_listar())
        elif caminho in ("/escritorio", "/escritorio/mesas"):
            # /escritorio e a cena 3D; /escritorio/mesas e a lista, para onde a 3D cai se o three.js nao carregar
            corpo = (escritorio3d.PAGINA if caminho == "/escritorio" else ESCRITORIO).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)
        elif caminho == "/gestao":
            corpo = gestao.PAGINA.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)
        elif caminho in gestao.CONSULTAS:
            try:
                self._json(gestao.CONSULTAS[caminho](parse_qs(urlparse(self.path).query)))
            except (ValueError, OSError) as err:
                self._json({"ok": False, "erro": str(err)}, 400)
        elif caminho == "/api/escritorio":
            self._json(_escritorio())
        elif caminho.startswith("/v/"):
            achado = _resolver(caminho[3:])
            if not achado:
                self.send_error(404)
                return
            self._arquivo(achado[2])
        else:
            self.send_error(404)

    def _arquivo(self, arq):
        tamanho = arq.stat().st_size
        ini, fim = 0, tamanho - 1
        faixa = self.headers.get("Range", "")
        parcial = faixa.startswith("bytes=")
        if parcial:
            a, _, b = faixa[6:].partition("-")
            try:
                ini = int(a) if a else max(0, tamanho - int(b))
                fim = min(tamanho - 1, int(b)) if (a and b) else tamanho - 1
            except ValueError:
                ini, fim = 0, tamanho - 1
        if ini > fim or ini >= tamanho:
            self.send_error(416)
            return
        self.send_response(206 if parcial else 200)
        self.send_header("Content-Type", mimetypes.guess_type(arq.name)[0] or "video/mp4")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(fim - ini + 1))
        if parcial:
            self.send_header("Content-Range", f"bytes {ini}-{fim}/{tamanho}")
        self.end_headers()
        try:
            with open(arq, "rb") as f:
                f.seek(ini)
                falta = fim - ini + 1
                while falta > 0:
                    bloco = f.read(min(256 * 1024, falta))
                    if not bloco:
                        break
                    self.wfile.write(bloco)
                    falta -= len(bloco)
        except (BrokenPipeError, ConnectionError):
            pass

    def do_POST(self):
        if self.path not in ("/api/acao", "/api/expediente", "/api/pedido", *gestao.ACOES):
            self.send_error(404)
            return
        # exigir Origin proprio e JSON declarado impede que outra pagina aberta no navegador mexa nos cortes
        porta = self.server.server_address[1]
        if (not self._local() or self.headers.get("Origin") not in (f"http://127.0.0.1:{porta}", f"http://localhost:{porta}")
                or "application/json" not in self.headers.get("Content-Type", "")):
            self.send_error(403)
            return
        try:
            n = int(self.headers.get("Content-Length", "0"))
            if not 0 < n <= 100_000:
                raise ValueError("tamanho invalido")
            dados = json.loads(self.rfile.read(n))
            campos = dados.get("campos") if isinstance(dados, dict) else None
            if not isinstance(dados, dict) or not isinstance(campos, (dict, type(None))):
                raise ValueError("formato invalido")
            if self.path in gestao.ACOES:
                self._json({"ok": True, **gestao.ACOES[self.path](dados)})
                return
            if self.path == "/api/pedido":
                self._json({"ok": True, **_pedido(str(dados.get("url", "")), str(dados.get("time", "")), dados.get("cortes"),
                                                  str(dados.get("jogo", "")))})
                return
            if self.path == "/api/expediente":
                self._json({"ok": True, "vigia": _expediente(str(dados.get("acao", "")))})
                return
            if dados.get("acao") == "comentar":
                ok, erro = _comentar(str(dados.get("id", "")), (campos or {}).get("comentario", ""))
                self._json({"ok": ok, "erro": erro}, 200 if ok else 400)
                return
            ok = _mover(str(dados.get("id", "")), str(dados.get("acao", "")), campos)
        except (ValueError, OSError) as e:
            self._json({"ok": False, "erro": str(e)}, 400)
            return
        self._json({"ok": ok}, 200 if ok else 400)


def servir(porta=8765, pagina="/"):
    servidor = ThreadingHTTPServer(("127.0.0.1", porta), Tela)
    link = f"http://127.0.0.1:{porta}{pagina}"
    log(f"Tela de revisao em {link}  (feche esta janela ou Ctrl+C para encerrar)")
    try:
        webbrowser.open(link)
    except Exception:
        pass
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass


PAGINA = r"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Aprovação</title>
<style>
  :root {
    --fundo: #070a11; --painel: #0e131d; --borda: #26303f; --texto: #f1ece0; --fraco: #9aa3b2;
    --destaque: #d4af5a; --latao2: #8f7434; --ok: #3ddc84; --ruim: #ff5d5d; --campo: #080b12;
    --serifa: "Playfair Display", "Bodoni MT", Didot, Georgia, "Times New Roman", serif;
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--fundo); color: var(--texto);
         font: 15px/1.45 system-ui, "Segoe UI", sans-serif; }
  header { position: sticky; top: 0; z-index: 5; background: linear-gradient(#0f1522, #0a0e17);
           border-bottom: 1px solid var(--latao2); padding: 10px 20px; display: flex; flex-wrap: wrap; gap: 10px 22px; align-items: center; }
  h1 { font-family: var(--serifa); font-size: 19px; letter-spacing: .14em; text-transform: uppercase; color: var(--destaque);
       margin: 0; font-weight: 700; }
  nav { display: flex; gap: 4px; }
  nav a { color: var(--fraco); text-decoration: none; padding: 6px 12px; border-radius: 6px; font-size: 13px;
          letter-spacing: .04em; text-transform: uppercase; }
  nav a:hover { color: var(--texto); }
  nav a[aria-current] { color: var(--destaque); background: #1a2231; }
  nav a:focus-visible { outline: 2px solid var(--destaque); outline-offset: 2px; }
  .barra { display: flex; flex-wrap: wrap; gap: 10px 16px; align-items: center; padding: 14px 20px 0; }
  .barra h2 { font: 700 24px/1.2 var(--serifa); margin: 0 10px 0 0; }
  article:hover { border-color: var(--latao2); }
  .trilha { list-style: none; margin: 8px 0 0; padding: 0; display: grid; gap: 8px; }
  .trilha li { border-left: 2px solid var(--borda); padding-left: 10px; color: var(--texto); }
  .trilha li.aprovado, .trilha li.promovido, .trilha li.entregue { border-color: var(--ok); }
  .trilha li.reprovado { border-color: var(--ruim); }
  .trilha li.resgatado, .trilha li.puxado, .trilha li.ausente { border-color: var(--destaque); }
  .trilha b { font-weight: 600; }
  .trilha small { display: block; color: var(--fraco); }
  .trilha .melhoria { color: var(--destaque); }
  .abas { display: flex; gap: 6px; }
  .abas button { background: transparent; color: var(--fraco); border: 1px solid var(--borda); border-radius: 999px;
                 padding: 6px 14px; font: inherit; cursor: pointer; }
  .abas button[aria-pressed="true"] { background: var(--destaque); color: #1a1206; border-color: var(--destaque); font-weight: 600; }
  select { background: var(--campo); color: var(--texto); border: 1px solid var(--borda); border-radius: 8px;
           padding: 6px 10px; font: inherit; margin-left: auto; }
  main { padding: 20px; display: grid; gap: 18px; grid-template-columns: repeat(auto-fill, minmax(290px, 1fr)); }
  .vazio { grid-column: 1 / -1; color: var(--fraco); padding: 48px 0; text-align: center; }
  article { background: var(--painel); border: 1px solid var(--borda); border-radius: 12px; overflow: hidden;
            display: flex; flex-direction: column; box-shadow: 0 12px 30px #0007; }
  video { width: 100%; aspect-ratio: 9 / 16; background: #000; display: block; }
  .corpo { padding: 12px 14px 14px; display: flex; flex-direction: column; gap: 10px; }
  .linha { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; color: var(--fraco); font-size: 13px; }
  .canal { color: var(--texto); font: 700 17px/1.2 var(--serifa); }
  .nota { margin-left: auto; font-variant-numeric: tabular-nums; font-weight: 700; color: var(--fundo);
          background: var(--destaque); border-radius: 6px; padding: 1px 8px; }
  .campo { display: flex; flex-direction: column; gap: 4px; }
  .dupla { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
  .campo span { font-size: 12px; color: var(--fraco); }
  input[type=text], textarea { width: 100%; background: var(--campo); color: var(--texto);
                     border: 1px solid var(--borda); border-radius: 8px; padding: 8px 10px; font: inherit; }
  textarea { resize: vertical; min-height: 4.6em; font-size: 14px; }
  input[type=text]:focus-visible, textarea:focus-visible, button:focus-visible, select:focus-visible {
                     outline: 2px solid var(--destaque); outline-offset: 2px; }
  .motivo { font-size: 13px; color: var(--fraco); margin: 0; }
  .etiqueta { font-size: 12px; border: 1px solid var(--borda); border-radius: 999px; padding: 2px 9px; color: var(--texto); }
  .etiqueta.atencao { border-color: var(--destaque); color: var(--destaque); }
  .etiqueta.alerta { border-color: var(--ruim); color: var(--ruim); }
  button:disabled { opacity: .55; cursor: progress; }
  details { font-size: 13px; color: var(--fraco); }
  details p { margin: 6px 0 0; overflow-wrap: anywhere; }
  .botoes { display: flex; gap: 6px; flex-wrap: wrap; }
  .botoes button { flex: 1 1 auto; background: transparent; color: var(--texto); border: 1px solid var(--borda);
                   border-radius: 8px; padding: 7px 10px; font: inherit; font-size: 13px; cursor: pointer; }
  .botoes button:hover { border-color: var(--fraco); }
  .decisao button { font-size: 15px; font-weight: 600; padding: 9px 10px; }
  .decisao .sim { background: var(--destaque); border-color: var(--destaque); color: #1a1206; }
  .decisao .nao { color: var(--ruim); border-color: color-mix(in srgb, var(--ruim) 55%, transparent); }
  #aviso { position: fixed; left: 50%; bottom: 22px; transform: translateX(-50%); background: var(--texto);
           color: var(--fundo); padding: 8px 16px; border-radius: 999px; font-size: 14px; opacity: 0;
           transition: opacity .2s; pointer-events: none; }
  #aviso.visivel { opacity: 1; }
  @media (max-width: 520px) { header { padding: 12px 16px; } main { padding: 16px; } select { margin-left: 0; } }
  @media (prefers-reduced-motion: reduce) { #aviso { transition: none; } }
</style>
</head>
<body>
<header>
  <h1 id="marca">ClipeMax</h1>
  <nav>
    <a href="/escritorio">Escritório</a>
    <a href="/" aria-current="page">Aprovação</a>
    <a href="/escritorio/mesas">Lista</a>
    <a href="/gestao">Gestão</a>
  </nav>
</header>
<div class="barra">
  <h2>Mesa do CEO</h2>
  <div class="abas" id="abas"></div>
  <select id="canal" aria-label="Filtrar por canal"></select>
</div>
<main id="lista"></main>
<div id="aviso" role="status"></div>
<script>
const NOMES = { ceo: "Para você aprovar", analise: "Em análise", aprovado: "Aprovados", descartado: "Descartados" };
const ETAPAS = { lider_time: "com o líder do time", qualidade: "na qualidade", compliance: "no compliance",
                 gerente: "com o gerente de conteúdo", diretor: "na reserva do diretor editorial" };
fetch("/api/escritorio").then(r => r.json()).then(q => { document.getElementById("marca").textContent = q.empresa; }).catch(() => {});
let cortes = [], aba = "ceo", canal = "";

const el = (tag, props = {}, filhos = []) => {
  const n = Object.assign(document.createElement(tag), props);
  filhos.forEach(f => n.append(f));
  return n;
};
function avisar(txt) {
  const a = document.getElementById("aviso");
  a.textContent = txt; a.classList.add("visivel");
  clearTimeout(avisar.t); avisar.t = setTimeout(() => a.classList.remove("visivel"), 1600);
}
async function copiar(txt, rotulo) {
  if (!txt) { avisar(rotulo + " está vazio"); return; }
  let ok = false;
  try { await navigator.clipboard.writeText(txt); ok = true; } catch {}
  if (!ok) {
    // alguns navegadores bloqueiam a area de transferencia: copia por um campo temporario
    const tmp = el("textarea", { value: txt });
    tmp.style.cssText = "position:fixed;top:0;left:0;opacity:0";
    document.body.append(tmp);
    tmp.select();
    try { ok = document.execCommand("copy"); } catch {}
    tmp.remove();
  }
  avisar(ok ? rotulo + " copiado" : "O navegador bloqueou a cópia");
}
async function carregar() {
  cortes = await (await fetch("/api/cortes")).json();
  desenhar();
}
async function agir(c, acao, campos) {
  if (acao !== "salvar") {
    // solta o arquivo antes de mover: o Windows nao move um video que o player ainda esta lendo
    document.querySelectorAll("video").forEach(v => {
      if (v.dataset.id === c.id) { v.pause(); v.removeAttribute("src"); v.load(); }
    });
    await new Promise(r => setTimeout(r, 150));
  }
  const r = await fetch("/api/acao", { method: "POST", headers: { "Content-Type": "application/json" },
                                       body: JSON.stringify({ id: c.id, acao, campos }) });
  if (!r.ok) {
    avisar(acao === "salvar" ? "Não consegui salvar" : "Não consegui mover o arquivo");
    if (acao !== "salvar") carregar();
    return false;
  }
  if (acao === "salvar") { avisar("Salvo"); return true; }
  avisar({ aprovar: "Aprovado", descartar: "Descartado", restaurar: "Voltou para a sua fila", puxar: "Veio para a sua fila" }[acao]);
  carregar();
  return true;
}
function campo(rotulo, valor, linhas) {
  const entrada = linhas ? el("textarea", { value: valor, rows: linhas }) : el("input", { type: "text", value: valor });
  const caixa = el("label", { className: "campo" }, [el("span", { textContent: rotulo }), entrada]);
  return [caixa, entrada];
}
function cartao(c) {
  const [cxTitulo, titulo] = campo("Título", c.titulo);
  const [cxTiktok, tiktok] = campo("Legenda do TikTok", c.tiktok, 3);
  const [cxShorts, shorts] = campo("Legenda do Shorts", c.shorts, 3);
  const campos = () => ({ titulo: titulo.value.trim(), tiktok: tiktok.value.trim(), shorts: shorts.value.trim() });
  [titulo, tiktok, shorts].forEach(e => e.addEventListener("change", async () => {
    if (await agir(c, "salvar", campos())) Object.assign(c, campos());
  }));
  const bt = (txt, fn, cls = "") => el("button", { type: "button", textContent: txt, className: cls, onclick: fn });
  const topo = el("div", { className: "linha" }, [el("span", { className: "canal", textContent: c.canal })]);
  if (c.trecho) topo.append(el("span", { textContent: c.trecho.split(" a ")[0] }));
  if (c.duracao) topo.append(el("span", { textContent: Math.round(c.duracao) + "s" }));
  if (c.nota_ia !== null && c.nota_ia !== undefined)
    topo.append(el("span", { className: "nota", textContent: c.nota_ia + "/10", title: "Nota da IA" }));
  const corpo = el("div", { className: "corpo" }, [topo]);
  const avisos = el("div", { className: "linha" });
  if (c.jogo && c.jogo !== "nenhum") avisos.append(el("span", { className: "etiqueta", textContent: c.jogo }));
  if (c.musica === "destaque") avisos.append(el("span", { className: "etiqueta alerta",
    textContent: "Música em destaque (" + c.musica_pct + "%)", title: "Risco de bloqueio ou silenciamento por direitos autorais" }));
  else if (c.musica === "fundo") avisos.append(el("span", { className: "etiqueta atencao",
    textContent: "Música de fundo (" + c.musica_pct + "%)", title: "Pode gerar reivindicação; mantenha o Short com até 60 s" }));
  if (c.cutscene) avisos.append(el("span", { className: "etiqueta alerta", textContent: "Possível cutscene",
    title: "Cena de história isolada: é spoiler e costuma ser removida a pedido da produtora" }));
  if (c.ofensas) avisos.append(el("span", { className: "etiqueta atencao", textContent: "Xingamento pesado no áudio",
    title: "A legenda foi mascarada, mas a palavra continua sendo ouvida; a plataforma pode restringir o vídeo" }));
  if (avisos.children.length) corpo.append(avisos);
  if (c.motivo) corpo.append(el("p", { className: "motivo", textContent: c.motivo }));
  if (c.fila === "analise") corpo.append(el("p", { className: "motivo", textContent: "Ainda " + (ETAPAS[c.etapa] || "na esteira") + "." }));
  if (c.trilha.length) {
    // o caminho do corte pela empresa: quem viu, o que decidiu e por que
    const trilha = el("details", { open: c.fila === "ceo" }, [el("summary", { textContent: "Pareceres da equipe (" + c.trilha.length + ")" })]);
    trilha.append(el("ul", { className: "trilha" }, c.trilha.map(p => {
      const item = el("li", { className: p.veredito }, [el("b", { textContent: p.quem }), document.createTextNode(" · " + p.veredito)]);
      if (p.parecer) item.append(el("small", { textContent: p.parecer }));
      if (p.melhoria) item.append(el("small", { className: "melhoria", textContent: "Melhorar: " + p.melhoria }));
      return item;
    })));
    const antes = Object.entries(c.antes_do_gestor || {}).filter(([, v]) => v);
    if (antes.length) trilha.append(el("p", { textContent: "Texto antes do gestor: " + antes.map(([k, v]) => k + " = " + v).join(" | ") }));
    corpo.append(trilha);
  }
  if (c.postado_youtube) corpo.append(el("p", { className: "motivo", textContent: "Postado no YouTube: " + c.postado_youtube }));
  if (c.postado_tiktok) corpo.append(el("p", { className: "motivo", textContent: "Enviado como rascunho ao TikTok." }));
  corpo.append(cxTitulo, cxTiktok, cxShorts);
  const [cxComent, coment] = campo("Seu comentário no vídeo", c.comentario || c.contexto, 2);
  coment.maxLength = 160;
  const dica = el("p", { className: "motivo", textContent: c.comentario
    ? "Este comentário está no vídeo. Edite e aplique de novo, ou apague o texto e aplique para tirar."
    : (c.contexto ? "Rascunho de contexto escrito pela IA. Reescreva com a sua opinião e aplique." : "Aparece numa caixa no topo do vídeo.") });
  const aplicar = bt("Aplicar comentário no vídeo", async () => {
    aplicar.disabled = true; aplicar.textContent = "Renderizando...";
    document.querySelectorAll("video").forEach(v => { if (v.dataset.id === c.id) { v.pause(); v.removeAttribute("src"); v.load(); } });
    await new Promise(r => setTimeout(r, 150));
    const r = await fetch("/api/acao", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: c.id, acao: "comentar", campos: { comentario: coment.value.trim() } }) });
    const j = await r.json().catch(() => ({}));
    avisar(r.ok ? (coment.value.trim() ? "Comentário aplicado" : "Comentário removido") : "Não deu: " + (j.erro || "erro"));
    carregar();
  });
  corpo.append(cxComent, dica, el("div", { className: "botoes" }, [aplicar]));
  corpo.append(el("div", { className: "botoes" }, [
    bt("Copiar título", () => copiar(titulo.value.trim(), "Título")),
    bt("Copiar TikTok", () => copiar(tiktok.value.trim(), "Legenda do TikTok")),
    bt("Copiar Shorts", () => copiar(shorts.value.trim(), "Legenda do Shorts")),
    bt("Copiar caminho", () => copiar(c.caminho, "Caminho do arquivo")),
  ]));
  const det = el("details", {}, [el("summary", { textContent: "Detalhes" })]);
  [["Gancho", c.gancho], ["Sinais", c.sinais], ["Enquadramento", c.enquadramento], ["Fala", c.fala],
   ["Arquivo", c.pasta + "/" + c.arquivo + " (" + c.mb + " MB)"]]
    .filter(([, v]) => v).forEach(([k, v]) => det.append(el("p", { textContent: k + ": " + v })));
  corpo.append(det);
  const decisao = el("div", { className: "botoes decisao" });
  if (c.fila === "ceo") {
    decisao.append(bt("Aprovar", () => agir(c, "aprovar", campos()), "sim"),
                   bt("Descartar", () => agir(c, "descartar", null), "nao"));
  } else if (c.fila === "analise") {
    decisao.append(bt("Puxar para a minha fila", () => agir(c, "puxar", null)));
  } else {
    if (c.estado === "aprovado") {
      // desempenho: anote as views depois de postar; o relatorio "cortes.bat --desempenho" usa esses numeros
      const [cxVt, vt] = campo("Views no TikTok", c.views_tiktok ?? "");
      const [cxVs, vs] = campo("Views no Shorts", c.views_shorts ?? "");
      [vt, vs].forEach(e => { e.inputMode = "numeric"; e.placeholder = "depois de postar"; });
      [vt, vs].forEach(e => e.addEventListener("change", () =>
        agir(c, "salvar", { views_tiktok: vt.value, views_shorts: vs.value })));
      corpo.append(el("div", { className: "dupla" }, [cxVt, cxVs]));
    }
    decisao.append(bt("Voltar para a minha fila", () => agir(c, "restaurar", campos())));
  }
  corpo.append(decisao);
  const vid = el("video", { controls: true, preload: "metadata", playsInline: true });
  vid.dataset.id = c.id;
  vid.src = "/v/" + c.id.split("/").map(encodeURIComponent).join("/") + "?v=" + c.versao + "#t=0.5";
  vid.addEventListener("play", () => document.querySelectorAll("video").forEach(v => { if (v !== vid) v.pause(); }));
  return el("article", {}, [vid, corpo]);
}
function desenhar() {
  const abas = document.getElementById("abas");
  abas.replaceChildren(...Object.keys(NOMES).map(k => {
    const b = el("button", { type: "button", textContent: NOMES[k] + " (" + cortes.filter(c => c.fila === k).length + ")" });
    b.setAttribute("aria-pressed", String(k === aba));
    b.onclick = () => { aba = k; desenhar(); };
    return b;
  }));
  const daAba = cortes.filter(c => c.fila === aba);
  const canais = [...new Set(daAba.map(c => c.canal))].sort();
  if (canal && !canais.includes(canal)) canal = "";
  const sel = document.getElementById("canal");
  sel.replaceChildren(el("option", { value: "", textContent: "Todos os canais" }),
                      ...canais.map(n => el("option", { value: n, textContent: n })));
  sel.value = canal;
  sel.onchange = () => { canal = sel.value; desenhar(); };
  const visiveis = daAba.filter(c => !canal || c.canal === canal)
                        .sort((a, b) => (b.nota_gestor ?? b.nota_ia ?? -1) - (a.nota_gestor ?? a.nota_ia ?? -1));
  const lista = document.getElementById("lista");
  if (!visiveis.length) {
    lista.replaceChildren(el("p", { className: "vazio", textContent: aba === "ceo"
      ? "Nada esperando a sua decisão. O que a equipe ainda está analisando fica na aba Em análise." : "Nada aqui ainda." }));
    return;
  }
  lista.replaceChildren(...visiveis.map(cartao));
}
carregar();
</script>
</body>
</html>
"""


ESCRITORIO = r"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Equipe</title>
<style>
  :root {
    --fundo: #070a11; --painel: #0e131d; --painel2: #141b28; --borda: #26303f; --texto: #f1ece0; --fraco: #9aa3b2;
    --latao: #d4af5a; --latao2: #8f7434; --alta: #3ddc84; --baixa: #ff5d5d; --ambar: #f0a63a;
    --serifa: "Playfair Display", "Bodoni MT", Didot, Georgia, "Times New Roman", serif;
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--fundo); color: var(--texto); font: 15px/1.5 system-ui, "Segoe UI", sans-serif; }
  header { display: flex; align-items: center; gap: 12px 22px; padding: 10px 20px; flex-wrap: wrap; position: sticky; top: 0; z-index: 5;
           background: linear-gradient(#0f1522, #0a0e17); border-bottom: 1px solid var(--latao2); }
  .marca { font-family: var(--serifa); font-size: 19px; letter-spacing: .14em; text-transform: uppercase; color: var(--latao);
           margin: 0; font-weight: 700; }
  nav { display: flex; gap: 4px; }
  nav a { color: var(--fraco); text-decoration: none; padding: 6px 12px; border-radius: 6px; font-size: 13px;
          letter-spacing: .04em; text-transform: uppercase; }
  nav a:hover { color: var(--texto); }
  nav a[aria-current] { color: var(--latao); background: #1a2231; }
  #hora { margin-left: auto; color: var(--fraco); font-size: 13px; font-variant-numeric: tabular-nums; }
  main { padding: 24px 20px 48px; display: grid; gap: 30px; max-width: 1240px; margin: 0 auto; }
  h2 { font: 700 22px/1.2 var(--serifa); color: var(--latao); margin: 0 0 4px; }
  .sub { color: var(--fraco); font-size: 13px; margin: 0 0 14px; }
  .sala { display: grid; gap: 14px; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); }
  .times { grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); }
  .mesa { background: var(--painel); border: 1px solid var(--borda); border-radius: 12px; padding: 16px; display: grid; gap: 8px;
          align-content: start; }
  .mesa.chefe { border-color: var(--latao2); background: linear-gradient(160deg, #161d2b, var(--painel)); }
  .mesa h3 { margin: 0; font: 700 17px/1.2 var(--serifa); }
  .cargo, .linha { color: var(--fraco); font-size: 13px; margin: 0; }
  .numero { font: 700 30px/1 var(--serifa); font-variant-numeric: tabular-nums; }
  .numero small { font: 400 13px system-ui, sans-serif; color: var(--fraco); }
  .humor { justify-self: start; border-radius: 999px; padding: 2px 10px; font-size: 12px; font-weight: 700; background: var(--latao); color: #1a1206; }
  .humor.animado { background: var(--alta); } .humor.cauteloso { background: var(--ambar); } .humor.pressao { background: var(--baixa); color: #fff; }
  .humor.fora { background: var(--borda); color: var(--fraco); }
  .trio { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
  .trio div { background: var(--painel2); border-radius: 8px; padding: 8px; text-align: center; font-size: 11px; color: var(--fraco); }
  .trio b { display: block; font: 700 20px/1.1 var(--serifa); color: var(--texto); font-variant-numeric: tabular-nums; }
  ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 4px; font-size: 13px; }
  li small { color: var(--fraco); }
  h4 { margin: 6px 0 0; font-size: 11px; letter-spacing: .1em; text-transform: uppercase; color: var(--fraco); font-weight: 600; }
  .aviso { color: var(--ambar); font-size: 12px; margin: 0; }
  .mesa a { color: var(--latao); font-size: 14px; }
  .caminho { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin: 0; padding: 0; list-style: none; font-size: 13px; }
  .caminho li { background: var(--painel); border: 1px solid var(--borda); border-radius: 999px; padding: 4px 12px; }
  .caminho li b { color: var(--latao); font-variant-numeric: tabular-nums; margin-right: 6px; }
  .caminho i { color: var(--latao2); font-style: normal; }
  .vazio { color: var(--fraco); }
  a:focus-visible { outline: 2px solid var(--latao); outline-offset: 2px; }
  @media (max-width: 520px) { main { padding: 18px 16px 40px; } #hora { display: none; } }
</style>
</head>
<body>
<header>
  <p class="marca" id="marca">ClipeMax</p>
  <nav>
    <a href="/escritorio">Escritório</a>
    <a href="/">Aprovação</a>
    <a href="/escritorio/mesas" aria-current="page">Lista</a>
    <a href="/gestao">Gestão</a>
  </nav>
  <span id="hora"></span>
</header>
<main>
  <section>
    <h2>Caminho de um corte</h2>
    <p class="sub">Cada etapa olha só o próprio domínio, grava o parecer e passa adiante. O número é quantos cortes estão parados ali agora.</p>
    <ul class="caminho" id="caminho"></ul>
  </section>
  <section><h2>Diretoria e gestão</h2><p class="sub">Quem valida depois que o time entrega.</p><div class="sala" id="gestao"></div></section>
  <section><h2>Times</h2><p class="sub">Um por streamer. O humor vem da sua taxa de aprovação nas últimas decisões e muda as regras do time.</p><div class="sala times" id="times"></div></section>
</main>
<script>
const el = (tag, props = {}, filhos = []) => {
  const n = Object.assign(document.createElement(tag), props);
  filhos.forEach(f => n.append(f));
  return n;
};
const p = (txt, cls = "linha") => el("p", { className: cls, textContent: txt });
const numero = (n, rotulo) => el("div", { className: "numero" }, [document.createTextNode(n + " "), el("small", { textContent: rotulo })]);
async function atualizar() {
  let q;
  try { q = await (await fetch("/api/escritorio")).json(); } catch { return; }
  document.getElementById("marca").textContent = q.empresa;
  document.title = "Equipe · " + q.empresa;
  document.getElementById("hora").textContent = "Atualizado às " + q.agora.slice(11, 19);
  const etapas = [["Times", q.times.reduce((s, t) => s + t.fila, 0)], ...q.gestao.map(g => [g.cargo, g.fila]), ["Você", q.ceo.fila]];
  document.getElementById("caminho").replaceChildren(...etapas.flatMap(([nome, n], i) => {
    const item = el("li", {}, [el("b", { textContent: String(n) }), document.createTextNode(nome)]);
    return i ? [el("i", { textContent: "›" }), item] : [item];
  }));
  document.getElementById("gestao").replaceChildren(
    ...q.gestao.map(g => el("div", { className: "mesa" }, [el("h3", { textContent: g.nome }), p(g.cargo, "cargo"), numero(g.fila, "na mesa"), p("Hoje: " + g.hoje)])),
    el("div", { className: "mesa chefe" }, [el("h3", { textContent: q.ceo.nome }), p("Aprovador final", "cargo"),
      numero(q.ceo.fila, q.ceo.fila === 1 ? "corte esperando você" : "cortes esperando você"), p("Hoje: " + q.ceo.hoje), el("a", { href: "/", textContent: "Abrir a fila de aprovação" })]));
  const times = document.getElementById("times");
  if (!q.times.length) { times.replaceChildren(el("p", { className: "vazio", textContent: "Nenhum canal no canais.txt ainda." })); return; }
  times.replaceChildren(...q.times.map(t => {
    const partes = [el("h3", { textContent: t.canal }), p(t.situacao, "cargo"),
      el("span", { className: "humor " + (t.ligado ? t.humor.nivel : "fora"), textContent: "Time " + t.humor.rotulo }),
      p(t.humor.decisoes ? Math.round(t.humor.taxa * 100) + "% de aprovação nas suas últimas " + t.humor.decisoes + " decisões. Efeito: " + t.humor.efeito + "."
                         : "Ainda sem decisões suas sobre este time."),
      el("div", { className: "trio" }, [[t.feitos_hoje, "feitos hoje"], [t.aprovados_hoje, "aprovados hoje"], [t.fila, "com o líder"]]
        .map(([n, r]) => el("div", {}, [el("b", { textContent: String(n) }), document.createTextNode(r)]))),
      el("h4", { textContent: "Equipe" }),
      el("ul", {}, t.pessoas.map(x => el("li", {}, [document.createTextNode(x.nome + " · " + x.cargo + " "), el("small", { textContent: x.faz })])))];
    if (t.feedback.length) partes.push(el("h4", { textContent: "Retorno recente dos gestores" }),
      el("ul", {}, t.feedback.map(f => el("li", {}, [document.createTextNode(f.texto + " "), el("small", { textContent: f.de })]))));
    if (!t.autorizado) partes.push(p("Canal sem autorização do streamer: a postagem fica bloqueada.", "aviso"));
    return el("div", { className: "mesa" }, partes);
  }));
}
atualizar();
setInterval(atualizar, 5000);
</script>
</body>
</html>
"""
