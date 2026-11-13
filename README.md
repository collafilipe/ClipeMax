# ClipeMax

Gera cortes verticais (TikTok e YouTube Shorts) a partir de lives da Twitch, Kick e YouTube.
Acha os melhores momentos pelo áudio, pelo chat e pelos clipes de espectadores, enquadra a webcam,
queima legenda karaokê e escreve título e legendas com IA. A postagem pode ser manual ou pelas APIs
oficiais (YouTube direto, TikTok como rascunho).

## Para o Claude que for instalar isto

Você está recebendo uma ferramenta pronta e testada no Windows 11. Sua tarefa é só instalar e
conferir que funciona, não reescrever. Passos:

1. Clone o repositório (ou extraia o zip) numa pasta sem acento no caminho, por exemplo `Documents\CortesGTA`.
2. Confirme os pré-requisitos (instale com `winget` se faltar, pedindo autorização ao usuário):
   - Python 3.12 (`winget install Python.Python.3.12`)
   - ffmpeg no PATH (`winget install Gyan.FFmpeg`)
   - Claude Code instalado e logado (comando `claude` no PATH). É ele que dá nota, título e
     legenda aos cortes, usando a assinatura do usuário, sem custo de API.
3. Rode `instalar.bat`. Ele cria a `.venv` e instala o `requirements.txt`.
4. Teste com uma live curta já encerrada:
   `cortes.bat "LINK_DA_LIVE" --cortes 3`
   Na primeira vez o modelo de legenda (Whisper "small", ~500 MB) é baixado sozinho.
5. Abra a tela de revisão: `cortes.bat --revisar` e acesse http://127.0.0.1:8765/

Cuidados conhecidos:
- Não atualize o `opencv-python-headless` para a série 5.x.
- Se o Windows bloquear a DLL do `jiter`, mantenha a versão fixada no `requirements.txt`.
- As fontes da legenda (Arial Black, Impact, Segoe UI Black) são do Windows.
- `chave_api.txt` é opcional (API paga da Anthropic) e esse caminho nunca foi testado. Sem o arquivo,
  a ferramenta usa o Claude Code instalado.
- Não rode renderização por GPU sem medir: no PC de origem foi mais lenta que a CPU.

## Instalar (neste ou em outro computador)

1. Coloque a pasta num caminho curto, por exemplo `Documentos\Business\corte colla`. Caminho muito
   longo estoura o limite de 260 caracteres do Windows nas pastas de cortes.
2. Dê dois cliques em `instalar.bat`. Ele confere Python 3.12 e ffmpeg (e oferece instalar pelo winget
   se faltarem), cria o ambiente, baixa as bibliotecas e põe o atalho **ClipeMax** na área de trabalho.
3. Instale o Claude Code e rode `claude` uma vez para entrar na conta. Sem ele os cortes saem sem
   nota, título e legenda da IA, e a gerência não dá parecer.
4. Abra pelo atalho (ou `iniciar.bat`). O escritório abre no navegador.

**Levar para outro PC:** rode `empacotar.bat`. Ele gera `clipemax.zip` (uns 14 MB) com o
código, o `canais.txt`, o `empresa.json` e as posições de webcam aprendidas. Ficam de fora o ambiente,
os vídeos, o estado do expediente e os segredos. No outro PC: extraia, rode `instalar.bat` e conecte
as contas de postagem de novo.

## Passar lives para os times

No escritório, cartão **Passar uma live para um time**: cole um link e clique em Enviar.

| Link | O que acontece |
|---|---|
| De um **canal** (`twitch.tv/NOME`, `kick.com/NOME`, `youtube.com/@NOME`) | Nasce um time para o canal e ele entra no `canais.txt`. Com o expediente aberto, a vigia passa a acompanhar e corta quando a live entrar no ar |
| De uma **live** (antiga ou no ar) | Entra na fila e é cortada uma vez, na quantidade de cortes que você pedir. Não precisa do expediente aberto |

Para uma live, você escolhe o time que cuida dela. "Time do próprio canal" usa o time do streamer; se
ele ainda não existe, é criado um time que **só trabalha nos links que você passar** (`vigiar=nao` no
`canais.txt`), sem acompanhar o canal sozinho. Momentos que já viraram corte são pulados.

Os cortes do pedido passam pela mesma cadeia de gestores e chegam à sua mesa.

## Uso do dia a dia

Tudo é feito pelo site, que abre pelo atalho **ClipeMax** (ou `iniciar.bat`). Não precisa de comando.

| O que fazer | Onde no site |
|---|---|
| Cortar uma live (antiga ou no ar) | Escritório → **Passar uma live para um time**: cole o link e escolha quantos cortes |
| Cortar só de um jogo | No mesmo cartão, campo "Só de um jogo". Para um time inteiro: Gestão → Times → "Só cortar este jogo" |
| Acompanhar os canais e cortar ao vivo | Escritório → **Abrir o expediente** |
| Acompanhar um canal novo | Gestão → Times → **Novo time** (ou cole o link do canal no cartão do Escritório) |
| Aprovar e reprovar cortes | **Aprovação** |
| Ver o desempenho de cada time | Gestão → **Desempenho** |
| Ver produção e receita estimada por canal | Gestão → **Desempenho** |
| Marcar que um streamer autorizou, mudar contrato e regras do time | Gestão → **Times** |
| Ver o que seria postado, sem enviar | Gestão → Postagem → **Ver o que seria postado** |
| Postar os aprovados | Gestão → Postagem → **Postar os aprovados** (YouTube sai privado, a menos que você escolha outra visibilidade) |
| Conectar a conta do YouTube ou do TikTok | Gestão → Postagem → **Conectar conta** |
| Trazer as views dos Shorts | Gestão → Postagem → **Atualizar views dos Shorts** |
| Mudar nomes da equipe e regras da aprovação | Gestão → **Empresa** |

Os comandos continuam existindo para quem preferir o terminal: `cortes.bat --help` lista todos.

## Modo agência: vários streamers ao mesmo tempo

A vigia analisa vários canais em paralelo (`--paralelos`, padrão 4). Só a etapa que usa o processador
inteiro (transcrever e renderizar) roda um corte por vez, e quem espera é atendido por prioridade.

Cada canal pode ter opções próprias no `canais.txt`, depois do link, separadas por `|`:

```
https://kick.com/NOME/videos | cliente=Fulano | autorizado=sim | prioridade=1 | por_hora=2 | mensalidade=800 | valor_mil_views=1.5
```

| Opção | Para que serve |
|---|---|
| `cliente` | Nome que aparece no painel e no log |
| `autorizado` | `sim` quando o streamer aceitou os cortes. Sem isso o painel marca SEM AUTORIZACAO |
| `prioridade` | 1 a 9. O 1 passa na frente na fila de transcrição e render |
| `por_hora`, `cortes`, `jogo`, `tags` | Trocam, só para este canal, a opção de mesmo nome da linha de comando |
| `mensalidade`, `valor_mil_views` | Valores do contrato, usados na receita estimada do painel |
| `funcionario` | Nome do líder do time deste canal no escritório e nos pareceres |
| `vigiar` | `nao` para um time que só trabalha nos links que você passar, sem acompanhar o canal |
| `conta` | Em qual conta conectada os cortes deste canal são postados (padrão `principal`) |

`cortes.bat --painel canais.txt --dias 30` mostra, por canal: cortes pendentes, aprovados e descartados,
taxa de aprovação, views anotadas na revisão e receita estimada (mensalidade + views × valor por mil).
É uma estimativa do contrato, não um extrato.

Capacidade de um PC, estimada a partir das medidas em `reports/` (não medida com muitos canais no ar):
cada corte custa perto de 80 s de processador (2,5 candidatos baixados e transcritos, legenda final e
render). Com 3 cortes por hora, cada canal ao vivo ocupa cerca de 4 minutos de processador por hora,
o que dá um teto teórico de uns 13 canais ao vivo ao mesmo tempo. Planeje no máximo 8 para ter folga.

Para mexer no código: `pip install -r requirements-dev.txt`, depois `python -m pytest` e
`python -m ruff check .`. Os testes cobrem a carteira, a fila, o painel, a esteira (com gestor simulado) e a postagem (com rede simulada); não cobrem download, IA nem render.

## A empresa: do time até você

Nenhum corte chega direto na sua tela. O desenho segue o fluxo de aprovação em etapas de empresas de
mídia: cada revisor olha só o próprio domínio, o corte não avança sem passar pela etapa atual, há um
único aprovador final (você) e tudo fica registrado com data.

| Etapa | Quem é | O que valida |
|---|---|---|
| Time (um por streamer) | Radar, Edição e Redação | Produzem: acham o momento, cortam e legendam, escrevem título e legendas |
| Líder do time | Gestor direto do time | A entrega está completa e na nota mínima do time? |
| Qualidade | Analista de qualidade | O vídeo está tecnicamente certo? Duração de 12 a 60 s, render inteiro, enquadramento |
| Compliance | Analista de compliance | Pode ser publicado? Música protegida, spoiler, ofensa, autorização do streamer |
| Gerência de conteúdo | Gerente (IA com rubrica de editor) | O corte se sustenta sozinho? Dá nota, reescreve título e legenda fracos |
| Diretoria editorial | Diretor | Pauta do dia: só os melhores de cada canal sobem (padrão 5 por dia) |
| CEO | Você | Vê o parecer de todos e decide. Só o que você aprova pode ser postado |

Cada etapa grava veredito, parecer e **o que melhorar**; o retorno aparece na ficha do time. Só a
gerência usa IA: as outras etapas são regras. Cinco IAs em fila custariam cinco vezes mais e tenderiam
a concordar entre si, sem pegar mais erro.

**Humor dos times.** Sai da sua taxa de aprovação nas últimas 10 decisões sobre cada canal (com menos
de 5 decisões o time fica em "normal") e muda a regra de verdade:

| Humor | Sua taxa de aprovação | Efeito |
|---|---|---|
| Animado | 70% ou mais | Ganha 1 vaga a mais na pauta do CEO |
| Normal | 40% a 69% | Regras padrão |
| Cauteloso | 20% a 39% | O líder exige 1 ponto a mais de nota |
| Sob pressão | Abaixo de 20% | O líder exige 2 pontos a mais e o time perde 1 vaga na pauta |

A esteira roda sozinha no fim de cada rodada da vigia; `cortes.bat --esteira` roda na hora.

Na tela (`cortes.bat --revisar`):

- **Aprovação:** a mesa do CEO. "Para você aprovar" traz só o que passou por todas as etapas, com os
  pareceres abertos. "Em análise" é o que ainda está com a equipe (dá para puxar), e "Descartados" é o
  que foi barrado, com o motivo (dá para resgatar).
- **Escritório:** um prédio térreo visto em corte, à noite, no meio de um jardim. Cada time tem a
  própria sala com quatro pessoas; qualidade, compliance, gerência, diretoria e a sua sala ficam do
  outro lado do corredor, e há sala de reunião, cozinha e lounge com sinuca.
  - **Abrir o expediente** (painel da esquerda) liga a vigia das lives sem abrir outra janela. É o que
    põe os times para acompanhar as lives, cortar e mandar os cortes pela cadeia até a sua mesa.
    "Fechar o expediente" encerra a vigia. Ela continua rodando se você fechar a tela de aprovação.
  - **Atividade dos agentes** e **Comunicação** mostram o que cada pessoa fez de verdade, direto do
    diário da produção e da esteira ("ouvindo a live de 2h10 até 2h20", "renderizando o corte",
    "barrou: música em destaque"). A tela do monitor só acende para quem está com trabalho na mão.
  - Quando um corte muda de etapa, alguém leva a fita até a mesa de quem valida em seguida. Aprovação
    sua faz o time comemorar.
  - As idas à cozinha e ao lounge são só ambiente; o ritmo delas segue o humor do time.
  - Clique numa sala para ver a ficha, ou use os botões do topo para ir a um cômodo.
    `?demo=1` no endereço mostra uma simulação, sem precisar da vigia.
- **Lista:** os mesmos dados sem 3D. É para onde o escritório cai se o three.js (carregado de CDN) não abrir.

`cortes.bat --avaliacao` mede a equipe pelas suas decisões: quanto cada etapa barrou por time, a taxa
de aprovação e o humor de cada time e, do que a gerência deixou subir, quanto você aprovou.

Para mudar nomes e regras, crie `empresa.json` só com o que quer trocar:

```json
{"nome": "Minha Agência", "gerente": "Gustavo", "diretor": "Lia", "cota_ceo_por_canal": 3, "nota_minima_gerente": 7}
```

`opcoes_da_vigia` no mesmo arquivo define as opções usadas quando o expediente é aberto pelo escritório,
por exemplo `"opcoes_da_vigia": "--jogo \"gta 6\" --por-hora 2"`.

A gerência usa o Claude Code instalado (a mesma assinatura da produção). Se a IA falhar numa rodada, os
cortes esperam na mesa dela; sem Claude Code instalado, sobem marcados como "sem parecer da gerência".
Produção e gerência são o mesmo modelo com instruções diferentes: a gerência pega erro de embalagem e
corte fraco, mas tende a concordar com a produção no gosto. Quem calibra os dois é a sua decisão.

As pessoas de cada time (Radar, Edição, Redação) são papéis de uma mesma execução automática, não
processos separados: a trilha mostra o que cada papel entregou, mas não dá para reprovar só a Redação
e mandar refazer. O retorno "o que melhorar" hoje é para você ler; ele ainda não muda a produção sozinho.

## Postagem

Só é postado o corte **aprovado** na revisão, de canal com `autorizado=sim` no `canais.txt`, e que ainda
não foi postado naquela plataforma. O resultado fica gravado no `.json` do corte, então rodar de novo
não duplica.

| Plataforma | O que acontece | Limite da API |
|---|---|---|
| YouTube | O vídeo é enviado com título e descrição. Sai **privado** por padrão; use `--visibilidade publico` quando confiar | 100 envios por dia por projeto |
| TikTok | O vídeo vai como **rascunho** para a caixa de entrada da conta. A legenda (campo "tiktok" do corte) é colada no aplicativo, onde você publica | 5 rascunhos pendentes a cada 24 h por conta |

Postar direto no TikTok exige o app auditado por eles; sem auditoria todo post sai privado. Por isso
este projeto usa o rascunho.

Configuração, uma vez só (os arquivos ficam em `segredos\`, que nunca vai para o git):

1. **YouTube:** no Google Cloud, crie um projeto, ative a "YouTube Data API v3", configure a tela de
   consentimento e crie uma credencial OAuth do tipo "App para computador". Baixe o JSON e salve como
   `segredos\youtube_app.json`. Deixe o app "Em produção": em modo de teste o Google derruba a conexão
   a cada 7 dias.
2. **TikTok:** no portal de desenvolvedores, crie um app com Login Kit e Content Posting API, escopo
   `video.upload`, e cadastre o retorno `http://localhost:8766/callback/`. Salve
   `{"client_key": "...", "client_secret": "..."}` como `segredos\tiktok_app.json`.
3. Conecte cada conta: `cortes.bat --conectar youtube` e `cortes.bat --conectar tiktok`. O navegador
   abre e o login é feito por você. Para mais de uma conta, use `--conta NOME` e ponha `conta=NOME`
   na linha do canal no `canais.txt`.

Esta parte foi testada só com respostas simuladas das APIs. Nunca rodou contra o YouTube ou o TikTok
de verdade: faça o primeiro envio com `--limite 1` e confira o vídeo privado antes de liberar o resto.


- `canais.txt`: canais acompanhados, um link por linha. Troque pelos seus.
- `palavras_mascaradas.txt`: xingamentos pesados que saem mascarados na legenda.
- `webcams.json`: posição da webcam de cada canal, aprendida sozinha.
- `prontos\`, `aprovados\`, `descartados\`: os cortes, criados no primeiro uso.
- `reports\`: análise da ferramenta e estudo do mercado de cortes em 2026. Vale ler o de mercado
  antes de postar: corte cru, sem valor próprio, perde alcance no YouTube.

## Antes de postar

Confira se o streamer permite cortes e as regras de vídeo da produtora do jogo. Cortes com aviso de
música, cutscene ou xingamento pesado aparecem marcados na tela de revisão.
