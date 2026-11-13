"""
Nota, titulo, gancho e legendas dos cortes, escritos pelo Claude. Ha dois caminhos:

  1. Assinatura (padrao, sem custo extra): usa o Claude Code instalado neste PC em modo automatico.
     Roda com a conta em que voce ja esta logado e conta no limite de uso do seu plano.
  2. API paga (opcional): se houver uma chave na variavel ANTHROPIC_API_KEY ou no arquivo
     chave_api.txt desta pasta, ela tem prioridade. E cobrada por uso.

Sem nenhum dos dois a ferramenta segue normalmente, escolhendo os cortes so pelos sinais.
"""
import base64
import json
import os
import shutil
import subprocess
import tempfile

from fontes import RAIZ, log

MODELO = "claude-opus-5-5"  # usado so no caminho da API paga
MODELO_ASSINATURA = "sonnet"  # no Claude Code: suficiente para titulos e gasta menos do limite do plano
ARQ_CHAVE = RAIZ / "chave_api.txt"

ESQUEMA = {
    "type": "object",
    "properties": {
        "cortes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "nota": {"type": "integer"},
                    "titulo": {"type": "string"},
                    "gancho": {"type": "string"},
                    "legenda_tiktok": {"type": "string"},
                    "legenda_shorts": {"type": "string"},
                    "jogo": {"type": "string"},
                    "contexto": {"type": "string"},
                    "cutscene": {"type": "boolean"},
                    "motivo": {"type": "string"},
                },
                "required": ["id", "nota", "titulo", "gancho", "legenda_tiktok", "legenda_shorts", "jogo", "contexto",
                             "cutscene", "motivo"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["cortes"],
    "additionalProperties": False,
}

SISTEMA = """Voce ajuda um canal brasileiro de cortes de lives (TikTok e YouTube Shorts) a decidir quais trechos valem ser postados.

Cada candidato e um trecho de 20 a 60 segundos de uma live, escolhido automaticamente porque o volume do audio subiu, o chat acelerou ou espectadores criaram clipes ali. Esses sinais dizem que algo aconteceu, mas nao o que: muitos candidatos sao so musica alta, tiroteio do jogo, o streamer lendo doacoes ou conversa sem graca. Voce recebe, de cada trecho, a transcricao da fala (feita por reconhecimento de voz, entao pode ter erros e palavras trocadas), os sinais que levaram a escolha e alguns quadros do video em ordem cronologica. Use os quadros para entender o que esta na tela: qual jogo e, o que o streamer esta fazendo, a reacao dele na webcam.

Para cada candidato, devolva:
- nota: inteiro de 0 a 10 para o potencial do trecho como video curto. Um bom corte se sustenta sozinho para quem nao viu a live: tem uma reacao forte, uma piada, uma jogada, uma historia curta ou uma fala marcante, com comeco e fim compreensiveis. De nota baixa quando a transcricao nao deixa claro o que aconteceu, quando o trecho depende de contexto que nao esta ali, ou quando quase nao ha fala e os sinais sao fracos.
- titulo: titulo em portugues do Brasil para o video, com no maximo 60 caracteres, especifico sobre o que acontece no trecho. Sem clickbait que o video nao entrega, sem hashtags e sem emojis.
- gancho: texto de 2 a 5 palavras, em portugues, que aparece na tela nos primeiros segundos para segurar quem esta rolando o feed. Deve criar curiosidade sobre o que vem a seguir sem entregar o desfecho.
- legenda_tiktok: a descricao que vai no post do TikTok. Uma frase curta e natural sobre o que acontece no trecho, no tom de quem posta cortes (pode ter um emoji), seguida de 4 a 6 hashtags em minusculas: o nome do streamer, o jogo que aparece no trecho e hashtags de alcance como #cortes e #fyp. Nao repita o titulo palavra por palavra.
- legenda_shorts: a descricao que vai no YouTube Shorts. Uma ou duas frases que descrevem o momento com as palavras que alguem digitaria na busca (nome do streamer, jogo, o que acontece), seguidas de 3 a 5 hashtags, sendo a ultima #shorts.
- jogo: o nome completo e oficial do jogo que aparece na tela durante o trecho, com o numero da edicao quando houver (por exemplo "Grand Theft Auto V", "Grand Theft Auto VI", "Super Mario Party Jamboree"). Se nao ha jogo na tela (o streamer so conversa, reage a videos ou esta em tela de espera), responda "nenhum". Se ha jogo mas voce nao consegue identificar qual, responda "desconhecido".
- contexto: uma frase de ate 90 caracteres, em portugues, que situa quem nao viu a live: o que estava acontecendo logo antes ou o que esta em jogo no trecho. E um rascunho para o dono do canal reescrever com a propria opiniao antes de colocar no video, entao escreva em tom neutro, sem repetir o titulo nem o gancho.
- cutscene: true se a maior parte do trecho e uma cena nao interativa da historia do jogo (cutscene, final, creditos ou uma revelacao importante do enredo), em que o streamer so assiste. Esses trechos sao spoiler e as produtoras costumam pedir a remocao quando sao postados isolados. Gameplay normal, mesmo de missao de historia, e false.
- motivo: uma frase curta explicando a nota, para quem vai revisar os cortes.

Os candidatos chegam em quantidade maior do que a que sera postada, e so os de nota mais alta viram video. Por isso use a escala inteira: reserve 8 a 10 para os poucos trechos que voce postaria sem pensar, de 5 a 7 para os que funcionam mas nao se destacam, e de 0 a 4 para os que nao valem a postagem. Dar a mesma nota media para todos nao ajuda na escolha.

As hashtags devem refletir o que esta de fato no trecho: so use a hashtag de um jogo se for esse o jogo na tela. Se a fala estiver em outro idioma, titulo, gancho e legendas continuam em portugues. Avalie cada candidato de forma independente e devolva todos, na mesma ordem e com o mesmo id."""


def _chave():
    chave = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not chave and ARQ_CHAVE.exists():
        bruto = ARQ_CHAVE.read_bytes()
        # o Bloco de Notas e o PowerShell podem gravar em UTF-16 ou com marca invisivel no comeco
        for cod in ("utf-8-sig", "utf-16"):
            try:
                chave = bruto.decode(cod).strip()
                break
            except UnicodeError:
                chave = ""
    # uma chave valida so tem letras, numeros, hifen e sublinhado
    return chave if chave and all(c.isascii() and (c.isalnum() or c in "-_") for c in chave) else ""


def modo():
    """'api' se ha chave paga configurada, 'assinatura' se o Claude Code esta instalado, '' se nenhum."""
    if _chave():
        try:
            import anthropic  # noqa: F401
            return "api"
        except ImportError:
            pass
    return "assinatura" if shutil.which("claude") else ""


def disponivel():
    return bool(modo())


def avaliar(candidatos, canal, titulo_live):
    """
    candidatos: [{"id", "trecho", "sinais", "fala", "quadros": [jpeg em bytes]}].
    Devolve {id: {"nota", "titulo", "gancho", "legenda_tiktok", "legenda_shorts", "motivo"}},
    ou None se a IA nao estiver configurada ou a chamada falhar.
    """
    if not candidatos:
        return None
    qual = modo()
    if not qual:
        return None
    dados = _pela_api(candidatos, canal, titulo_live) if qual == "api" else _pela_assinatura(candidatos, canal, titulo_live)
    if not dados:
        return None
    saida = {}
    for c in dados.get("cortes", []):
        try:
            saida[str(c["id"])] = {"nota": max(0, min(10, int(c["nota"]))), "titulo": str(c["titulo"]).strip()[:100],
                                   "gancho": str(c["gancho"]).strip()[:40], "motivo": str(c["motivo"]).strip(),
                                   "legenda_tiktok": str(c["legenda_tiktok"]).strip(),
                                   "legenda_shorts": str(c["legenda_shorts"]).strip(),
                                   "jogo": str(c.get("jogo", "")).strip(),
                                   "contexto": str(c.get("contexto", "")).strip()[:140],
                                   "cutscene": bool(c.get("cutscene", False))}
        except (KeyError, TypeError, ValueError):
            continue
    log(f"   IA: {len(saida)} de {len(candidatos)} cortes avaliados")
    return saida or None


def _pela_assinatura(candidatos, canal, titulo_live):
    """
    Usa o Claude Code instalado no PC em modo automatico (claude -p). Ele roda com a assinatura
    em que o usuario ja esta logado, entao nao ha cobranca por uso; conta no limite do plano.
    Os quadros vao como arquivos numa pasta temporaria, e a unica ferramenta liberada e a de leitura.
    """
    exe = shutil.which("claude")
    with tempfile.TemporaryDirectory(prefix="cortes_ia_") as pasta:
        partes = [f"Streamer: {canal}", f"Titulo da live: {titulo_live}", f"Sao {len(candidatos)} candidatos.",
                  "Os quadros de cada candidato estao em arquivos de imagem nesta pasta; abra cada um com a "
                  "ferramenta de leitura antes de avaliar."]
        for n, c in enumerate(candidatos):
            nomes = []
            for k, q in enumerate(c.get("quadros") or []):
                arq = os.path.join(pasta, f"cand{n:02d}_quadro{k + 1}.jpg")
                with open(arq, "wb") as f:
                    f.write(q)
                nomes.append(arq)
            partes.append(f"\n--- Candidato id={c['id']}\nTrecho: {c.get('trecho', '')}\nSinais: {c.get('sinais', '')}\n"
                          f"Fala: {c.get('fala') or '(sem fala reconhecida)'}\n"
                          f"Quadros: {', '.join(nomes) if nomes else '(nenhum)'}")
        return _rodar_claude_code(exe, "\n".join(partes), ESQUEMA, SISTEMA, pasta)


def _rodar_claude_code(exe, pedido, esquema, sistema, pasta):
    """Uma chamada do Claude Code em modo automatico, com resposta no esquema pedido. None se falhar."""
    cmd = [exe, "-p", "--output-format", "json", "--json-schema", json.dumps(esquema),
           "--system-prompt", sistema, "--tools", "Read", "--allowedTools", "Read",
           "--model", MODELO_ASSINATURA, "--no-session-persistence", "--strict-mcp-config"]
    try:
        r = subprocess.run(cmd, input=pedido, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", cwd=pasta, timeout=900)
    except subprocess.TimeoutExpired:
        log("   IA: o Claude Code demorou demais; sigo sem IA")
        return None
    try:
        resp = json.loads(r.stdout)
    except ValueError:
        log(f"   IA: o Claude Code nao respondeu como esperado ({(r.stderr or r.stdout).strip()[:160]}); sigo sem IA")
        return None
    if resp.get("is_error"):
        log(f"   IA: o Claude Code devolveu erro ({str(resp.get('result'))[:160]}); sigo sem IA")
        return None
    log(f"   IA (assinatura): resposta em {resp.get('duration_ms', 0) / 1000:.0f}s, {resp.get('num_turns', '?')} etapas")
    dados = resp.get("structured_output")
    if not isinstance(dados, dict):
        try:
            dados = json.loads(resp.get("result") or "")
        except ValueError:
            log("   IA: resposta em formato inesperado; sigo sem IA")
            return None
    return dados


ESQUEMA_GESTOR = {
    "type": "object",
    "properties": {
        "pareceres": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "nota": {"type": "integer"},
                    "veredito": {"type": "string", "enum": ["aprovar", "reprovar"]},
                    "parecer": {"type": "string"},
                    "melhoria": {"type": "string"},
                    "titulo": {"type": "string"},
                    "legenda_tiktok": {"type": "string"},
                    "legenda_shorts": {"type": "string"},
                },
                "required": ["id", "nota", "veredito", "parecer", "melhoria", "titulo", "legenda_tiktok", "legenda_shorts"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["pareceres"],
    "additionalProperties": False,
}

SISTEMA_GESTOR = """Voce e o gestor de conteudo de uma agencia brasileira de cortes de lives (TikTok e YouTube Shorts). Os cortes abaixo ja foram produzidos e passaram pela revisao tecnica. Depois de voce, o que for aprovado vai para o dono da agencia, que assiste um por um. O tempo dele e o recurso mais caro da empresa: seu trabalho e deixar subir so o que ele provavelmente aprovaria, e ja com o texto pronto.

Voce recebe, de cada corte, o titulo, o gancho e as legendas escritos por quem produziu, a transcricao da fala (reconhecimento de voz, pode ter erros), os sinais que levaram a escolha do trecho, os avisos do revisor tecnico e alguns quadros do video final, em ordem. Abra os quadros antes de julgar.

Julgue como editor, nao como quem escolheu o trecho. Reprove quando: quem nao viu a live nao entenderia o que acontece; o titulo promete algo que o trecho nao entrega; o momento e fraco (so barulho, leitura de doacao, conversa sem desfecho); dois cortes do mesmo lote mostram o mesmo momento ou a mesma piada (aprove so o melhor e diga qual o outro repete); ou ha algo que exporia a agencia ou o streamer (ofensa a grupo, acusacao a pessoa real, conteudo sexual).

Seu dominio e o conteudo. Autorizacao do streamer, direitos e bloqueio de postagem sao do compliance e do dono: nunca reprove nem baixe a nota por isso.

Para cada corte devolva:
- nota: inteiro de 0 a 10, a chance de o dono aprovar e de o video segurar quem esta rolando o feed. Use a escala inteira.
- veredito: "aprovar" ou "reprovar".
- parecer: uma ou duas frases para o dono, dizendo o que o corte tem de bom ou por que nao sobe. Seja especifico sobre o que aparece no trecho.
- melhoria: uma frase curta de retorno para o time que produziu, dizendo o que fazer diferente no proximo corte (por exemplo "comecar o corte dois segundos antes, na pergunta" ou "o titulo deve citar o que ele perdeu"). Fale com o time, nao com o dono. Se o corte esta redondo, devolva vazio.
- titulo, legenda_tiktok, legenda_shorts: a versao que deve ser publicada, em portugues do Brasil. Se o texto recebido ja esta bom, devolva igual. Se esta vazio, generico ou promete o que o video nao mostra, reescreva: titulo com no maximo 60 caracteres, sem emoji e sem hashtag; legenda do TikTok com uma frase natural e 4 a 6 hashtags em minusculas; legenda do Shorts com uma ou duas frases de busca e 3 a 5 hashtags, a ultima #shorts. So use hashtag de jogo que esteja de fato na tela.

Devolva todos os cortes, com o mesmo id recebido."""


def parecer_do_gestor(itens, canal):
    """
    Segunda leitura dos cortes prontos, com rubrica de editor (veja esteira.py).
    itens: [{"id", "titulo", "gancho", "legenda_tiktok", "legenda_shorts", "fala", "sinais", "duracao",
             "nota_do_clipador", "motivo_do_clipador", "avisos_do_revisor", "quadros": [jpeg em bytes]}]
    Devolve {id: {"nota", "veredito", "parecer", "melhoria", "titulo", "legenda_tiktok", "legenda_shorts"}} ou None se falhar.
    So roda pelo Claude Code instalado; o caminho da API paga nao foi escrito para o gestor.
    """
    exe = shutil.which("claude")
    if not exe or not itens:
        return None
    with tempfile.TemporaryDirectory(prefix="cortes_gestor_") as pasta:
        partes = [f"Streamer: {canal}", f"Sao {len(itens)} cortes deste canal, todos do mesmo lote.",
                  "Os quadros de cada corte estao em arquivos de imagem nesta pasta; abra cada um com a "
                  "ferramenta de leitura antes de julgar."]
        for n, c in enumerate(itens):
            nomes = []
            for k, q in enumerate(c.get("quadros") or []):
                arq = os.path.join(pasta, f"corte{n:02d}_quadro{k + 1}.jpg")
                with open(arq, "wb") as f:
                    f.write(q)
                nomes.append(arq)
            partes.append(
                f"\n--- Corte id={c['id']}\nDuracao: {c.get('duracao') or '?'}s\n"
                f"Titulo: {c.get('titulo') or '(vazio)'}\nGancho: {c.get('gancho') or '(vazio)'}\n"
                f"Legenda TikTok: {c.get('legenda_tiktok') or '(vazia)'}\n"
                f"Legenda Shorts: {c.get('legenda_shorts') or '(vazia)'}\n"
                f"Fala: {c.get('fala') or '(sem fala reconhecida)'}\nSinais: {c.get('sinais', '')}\n"
                f"Nota de quem produziu: {c.get('nota_do_clipador')} ({c.get('motivo_do_clipador') or 'sem motivo'})\n"
                f"Revisor tecnico: {c.get('avisos_do_revisor') or '-'}\n"
                f"Quadros: {', '.join(nomes) if nomes else '(nenhum)'}")
        dados = _rodar_claude_code(exe, "\n".join(partes), ESQUEMA_GESTOR, SISTEMA_GESTOR, pasta)
    if not dados:
        return None
    saida = {}
    for p in dados.get("pareceres", []):
        try:
            saida[str(p["id"])] = {"nota": int(p["nota"]), "veredito": str(p["veredito"]), "parecer": str(p["parecer"]),
                                   "melhoria": str(p.get("melhoria", "")),
                                   "titulo": str(p["titulo"]).strip()[:100],
                                   "legenda_tiktok": str(p["legenda_tiktok"]).strip(),
                                   "legenda_shorts": str(p["legenda_shorts"]).strip()}
        except (KeyError, TypeError, ValueError):
            continue
    return saida or None


def _pela_api(candidatos, canal, titulo_live):
    """Usa a API paga da Anthropic, com a chave de chave_api.txt ou da variavel de ambiente."""
    import anthropic

    pedido = [{"type": "text", "text": f"Streamer: {canal}\nTitulo da live: {titulo_live}\n"
                                       f"Sao {len(candidatos)} candidatos."}]
    for c in candidatos:
        pedido.append({"type": "text", "text": (
            f"\n--- Candidato id={c['id']}\nTrecho: {c.get('trecho', '')}\nSinais: {c.get('sinais', '')}\n"
            f"Fala: {c.get('fala') or '(sem fala reconhecida)'}\nQuadros deste candidato:")})
        for q in c.get("quadros") or []:
            pedido.append({"type": "image", "source": {
                "type": "base64", "media_type": "image/jpeg", "data": base64.standard_b64encode(q).decode("ascii")}})
    cliente = anthropic.Anthropic(api_key=_chave())
    try:
        # fallbacks="default": se o modelo recusar o pedido, a propria API tenta de novo em outro modelo
        resp = cliente.beta.messages.create(
            model=MODELO,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": "medium", "format": {"type": "json_schema", "schema": ESQUEMA}},
            system=SISTEMA,
            messages=[{"role": "user", "content": pedido}],
        )
    except anthropic.AuthenticationError:
        log("   IA: a chave da API foi recusada; sigo sem IA")
        return None
    except anthropic.RateLimitError:
        log("   IA: limite de uso atingido; sigo sem IA nesta rodada")
        return None
    except anthropic.APIStatusError as e:
        log(f"   IA: erro {e.status_code} da API ({str(e.message)[:120]}); sigo sem IA")
        return None
    except anthropic.APIConnectionError:
        log("   IA: sem conexao com a API; sigo sem IA")
        return None

    if resp.stop_reason == "refusal":
        log("   IA: o pedido foi recusado pelo modelo; sigo sem IA")
        return None
    if resp.stop_reason == "max_tokens":
        log("   IA: resposta cortada pelo limite de tamanho; sigo sem IA")
        return None
    texto = next((b.text for b in resp.content if b.type == "text"), "")
    try:
        dados = json.loads(texto)
    except ValueError:
        log("   IA: resposta em formato inesperado; sigo sem IA")
        return None
    log(f"   IA (API paga): {resp.usage.input_tokens} tokens de entrada, {resp.usage.output_tokens} de saida")
    return dados
