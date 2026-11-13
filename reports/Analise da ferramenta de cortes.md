# Análise da ferramenta de cortes

Data: 12 de novembro de 2026. Base: revisão independente de todo o código (5 módulos), testes reais feitos nesta sessão e o relatório de mercado em `Mercado de cortes de streamers 2026.md`.

## Situação das correções (atualizado em 12/11/2026)

Corrigidos e comprovados por teste:

- Item 1 (vigia gera cortes demais): simulação de 6 horas agora gera 18 cortes, exatamente a cota (antes 113).
- Item 2 (chat domina a nota): áudio e chat passaram para a mesma escala de raridade, com linha de base local de 15 minutos. Nos dados reais, dos 8 melhores momentos, 5 coincidem com pico de áudio, 5 com pico de chat e 2 com os dois (antes todos eram de chat).
- Item 3 (duplicados): em live real, 22 momentos já cortados foram pulados e saíram só 2 novos. O arquivo passou a ter o nome do momento do pico, que não muda entre execuções.
- Item 4 (acentos e emojis): título com emoji conferido em live real da Kick.
- Item 6 (aprovar com vídeo tocando): aprovado e restaurado com o vídeo em reprodução, sem ficar em duas pastas.
- Item 7 (gravação parcial): o corte é renderizado na pasta temporária e só então movido; nenhuma sobra temporária após o teste.
- Item 13 (pedidos de outros sites): pedidos com origem estranha, sem origem ou com outro nome de host são recusados (403); uso normal segue funcionando.

Corrigidos no código, sem teste específico:

- Item 5 (live sem cortes reprocessada), item 8 (live que reinicia, live agendada), item 9 (estado salvo logo após a análise, chat ausente não conta, falha de download é tentada de novo), item 10 (peso dos clipes por views absolutas; momentos antigos podem entrar em rodadas seguintes), item 11 (áudio truncado do YouTube vira erro), item 12 a e b (página quase vazia do chat, sonda antes de amostrar), itens 14, 15 e 16, item 19 (limpeza de temporários), item 21 (linha de legenda limitada por letras), e as hashtags fixas do item 23 (agora vêm da opção `--tags`).

Testes em lives reais no ar (12/11/2026, depois das correções):

- Modo vigia na Twitch (TenZ, live com 3 horas): primeira rodada leu as 3h04 já transmitidas e gerou 2 cortes em 375 s; a segunda rodada, 13 minutos depois, analisou só o trecho novo e gerou 1 corte em 139 s, fechando a cota de 3.
- Modo vigia na Kick (ogabdullah, live com 3 horas): primeira rodada em 192 s e segunda em 50 s, 1 corte em cada, cota de 2 respeitada. O teste revelou que a Kick marca a lista de segmentos como finalizada mesmo com a live no ar; a ferramenta passou a usar o estado "ao vivo" informado pela plataforma.
- Filtro de jogo: por capítulos na Twitch (só trechos de Phantom Blade Zero) e pela IA na Kick (pedido GTA 6 numa live de GTA V: os 5 candidatos foram descartados).
- IA pela assinatura do Claude, com 2,5 candidatos por corte: 7 cortes gerados em duas lives, todos com nota 5 ou mais.

Recursos pedidos pelas regras de 2026, feitos e testados em 12/11/2026:

- Música: detector com o modelo YAMNet (arquivos em `modelos/`). Validado com áudio real: música pura 100% em destaque, GTA com a rádio do carro 97% em destaque, GTA em perseguição sem rádio 0%, conversa sem jogo 0%. Cada corte sai marcado como sem música, música de fundo ou música em destaque; com música, o corte é limitado a 59 s. A opção `--sem-musica` descarta os cortes com música em destaque. O detector diz se há música, não se ela é protegida.
- Valor próprio: a IA escreve um rascunho de contexto por corte, e a tela de revisão tem um campo para o comentário do dono do canal, que é queimado no vídeo (cerca de 19 s por corte) e pode ser trocado ou removido sem perda, porque o vídeo sem comentário fica guardado ao lado com extensão `.base`.
- Variação de visual: cor de destaque da legenda, fonte e formato do gancho mudam de corte para corte (`--estilo-fixo` desliga).
- Spoiler: a IA marca possíveis cutscenes e a revisão mostra o aviso. Nenhum corte de teste tinha cutscene, então a marcação positiva não foi observada.

Ajustes posteriores, ainda em 12/11/2026:

- Vigia com prioridade para o recente: com a live no ar só entram momentos dos últimos 20 minutos; os bons momentos antigos que sobraram entram quando a live termina. Em simulação de 6 horas, 15 dos 18 cortes foram feitos até 30 minutos depois do momento e 3 no encerramento.
- Checagem do jogo antes de baixar: com `--jogo`, a vigia dispensa o canal sem baixar nada enquanto o streamer não está no jogo (capítulos na Twitch, categoria na Kick, título no YouTube). Uma rodada com 8 canais fora do jogo leva 15 s.
- Idioma automático por corte (`--idioma auto`, padrão).
- Enquadramento: se o rosto não é detectado num corte mas a posição da webcam do canal já é conhecida, e não há sinal de câmera em tela cheia, usa a posição conhecida em vez do fundo desfocado. Testado com detecções simuladas, não com vídeo real.
- A IA reconheceu cutscenes num teste real (live do Kai Cenat): dois candidatos foram apontados como "quase tudo é cutscene".

Velocidade e pendências menores, feitas e medidas em 12/11/2026:

| Etapa | Antes | Depois |
|---|---|---|
| Baixar o trecho de um candidato (70 s) | 12,6 s e 226 MB (recodificando) | 1,3 s e 66 MB (cópia direta) |
| Transcrever um candidato | 25 s | 12,6 s na triagem; só os escolhidos são refeitos com a busca cuidadosa |
| Analisar o áudio | dezenas de segundos por hora de live | cerca de 3 s por hora (segmentos em grupos) |
| Chat da Twitch, live de 6h20 | cerca de 2 minutos | 46 s (consultas em lotes) |
| Renderizar com fundo desfocado (45 s) | 63 s | 21 s (desfoque em resolução baixa) |
| Live de 9h29 da Kick, 8 candidatos com IA | 955 s | 328 s (sem renderizar, porque nenhum candidato passou) |

- Renderizar pela placa de vídeo (AMF) foi medido e descartado: 30 a 95 s contra 16,6 s do processador neste PC.
- Itens 12 c, 17 e 20 da lista de erros: chat da Twitch amostrado a cada 20 s, posição dos clipes da Kick tratada como faixa larga em vez de ponto, e corte exato no YouTube. Nenhum dos três teve teste específico.
- Ao rodar de novo a mesma live, os candidatos que a IA já reprovou não são reavaliados.
- Registro de desempenho: na aba Aprovados da revisão há campos para as views no TikTok e no Shorts, e `cortes.bat --desempenho` resume por streamer, jogo, enquadramento, nota da IA, música, duração e comentário. Ele só mostra os números; a escolha dos momentos ainda não muda sozinha com base neles.

Sem teste: a opção `--sem-musica` e o encurtamento para 59 s (nenhum corte de teste passou de 59 s).

Ainda sem teste real: o encerramento de uma live durante a vigia (só em simulação) e o YouTube com live em andamento.

Não corrigidos: item 12 c (rajadas curtas de chat), item 17 (posição dos clipes da Kick), item 18 (casos de borda da playlist), item 20 (deslocamento no YouTube), item 22 (desempenho) e a falta de testes automáticos.

## Resumo

A ferramenta funciona de ponta a ponta nas três plataformas e já tem o que o mercado trata como padrão: fusão de áudio, chat e clipes de espectadores, webcam em cima com jogo embaixo, legenda palavra a palavra com destaque de cor, modo ao vivo e fila de revisão. Os dois problemas principais são outros:

1. **Há erros que distorcem o resultado**, principalmente no modo vigia (gera cortes demais) e na nota dos momentos (o chat domina e o áudio quase não conta).
2. **O produto atual é exatamente o "corte cru" que as plataformas passaram a punir em 2026.** Falta a camada de valor próprio (contexto, comentário, variação), o tratamento de música e a adaptação por plataforma.

## O que foi medido nesta sessão

| Teste | Resultado |
|---|---|
| Live inteira da Twitch (6h20), fluxo novo | 6 cortes em 415 s |
| Live inteira da Kick (10h46), código antigo | 8 cortes em 1.227 s |
| Live inteira da Kick (10h46), fluxo novo | 8 cortes em 635 s |
| Modo vigia, simulado com live crescendo de 40 para 60 min | 2 cortes, depois silêncio, depois 1 corte novo |
| Tela de revisão | Lista, toca, edita, copia, aprova, descarta e restaura |
| IA (nota, título, gancho, legendas) | Não testada: sem chave de API neste PC |

Nunca testados: modo vigia com live real no ar, YouTube com live em andamento, a opção `--canais` em rodada completa, e se os momentos escolhidos são de fato bons (ninguém assistiu aos cortes julgando o conteúdo).

## Erros e fragilidades, por gravidade

"Confirmado" significa reproduzido rodando o código; "lido" significa identificado na leitura; "plausível" significa provável, sem reprodução.

### Graves: mudam o resultado

1. **Modo vigia gera cerca de 6 vezes os cortes pedidos** (confirmado). A cota por hora é do total da live, mas é aplicada de novo a cada rodada, e o limite afrouxa a cada rodada. Simulação de live de 6 horas com 3 cortes por hora: 113 cortes em vez de 18.
2. **O chat domina a nota; o áudio quase não conta** (confirmado em dados reais). Em 1 hora de live, o áudio chegou a 1,95 de nota e o chat a 11,2. Os 8 melhores momentos foram todos os picos de chat. Raids, trens de inscrição, comandos de bot e sorteios ganham de reações reais.
3. **Reprocessar a mesma live cria cortes duplicados e ressuscita os já revisados** (confirmado em disco). O mesmo momento aparece até 4 vezes na pasta do alanzoka. Um corte descartado volta como pendente.
4. **Emojis e acentos somem de títulos e nomes de canal** (confirmado em live real). Isso afeta o crédito queimado no vídeo, o nome da pasta, as hashtags e o texto enviado à IA.
5. **Live sem nenhum corte é reprocessada para sempre no modo vigia** (lido). A cada 10 minutos baixa o áudio inteiro de novo e, com IA, paga a avaliação de novo.
6. **Aprovar ou descartar com o vídeo tocando deixa o corte nas duas pastas** (confirmado). No Windows o arquivo aberto não pode ser removido depois de copiado.
7. **Cortes são gravados direto na pasta final** (lido). Falha no meio deixa arquivo quebrado aparecendo na revisão.

### Médios: falham em situações específicas

8. **Só o VOD mais recente é olhado** (lido). Se a live cai e reinicia, o final da anterior nunca é cortado. Uma live agendada no YouTube trava o canal inteiro.
9. **O modo vigia congela dados ruins no estado** (lido). Falha de rede vira trecho "plano" permanente, falha de chat vira zeros, e o estado só é salvo no fim da rodada.
10. **Clipes de espectadores quase não contam durante a live e têm peso errado depois** (lido). Chegam minutos depois da janela fechar, e um clipe com 3 views vale o mesmo que um com 50 mil se for o maior da live.
11. **Áudio do YouTube é truncado em silêncio se o download cair** (lido). A live é marcada como processada com cortes só do começo.
12. **Amostragem do chat da Twitch** (lido). Página com 1 mensagem vira pico falso; VOD só para inscritos gasta uns 15 minutos antes de desistir; rajadas curtas de chat podem ser perdidas.
13. **A tela de revisão aceita pedidos de outros sites** (lido, não explorado). Uma página aberta no navegador poderia aprovar, descartar ou alterar títulos.
14. **A etapa de IA pode derrubar a execução depois de todo o trabalho feito** (confirmado para arquivo de chave salvo com codificação errada). Com mais de uns 33 candidatos, cai para "sem IA" sem avisar.
15. **`canais.txt` salvo com marca de codificação quebra a primeira linha** (confirmado).
16. **Trecho baixado incompleto gera duração negativa**, depois de já ter gasto IA nele (confirmado na função).

### Menores

17. Posição dos clipes da Kick é uma estimativa (assume 15 s de atraso).
18. Casos de borda da playlist: segmentos silenciados da Twitch, links que expiram em execuções longas, e "live encerrada" decidido por um único sinal.
19. Sobras de arquivos temporários quando há erro.
20. No YouTube, o início do corte pode deslocar alguns segundos.
21. Legendas com três palavras longas podem ser cortadas nas bordas.
22. Desempenho: cada trecho é codificado duas vezes; quatro chamadas do yt-dlp por canal por rodada; um processo do ffmpeg por segmento de 10 s; na Kick a análise de áudio baixa vídeo.
23. Manutenção: hashtags `#gta6 #gtavi` fixas para qualquer jogo quando não há IA; nome do canal deduzido do nome da pasta; nenhum teste automático; `cortes.bat` quebra links com `&` e fecha a janela sem mostrar o erro.

Conferido e sem problema: concorrência entre as tarefas paralelas, proteção contra acesso a arquivos fora das pastas na revisão, e sincronia da legenda depois do recorte.

## O que o mercado pede e a ferramenta ainda não faz

O grau de confiança vem do relatório de mercado.

| Exigência do mercado | Situação na ferramenta | Confiança |
|---|---|---|
| Valor próprio em cada corte (YouTube reduz o alcance de reenvios; template e edição técnica não contam) | Só gancho e título da IA, sem espaço para comentário próprio; todos os cortes têm o mesmo visual | Alta na direção, baixa em quanto basta |
| Short de mais de 1 minuto com música reivindicada é bloqueado | Não detecta música; duração alvo de 45 s fica abaixo do limite, mas nada impede passar | Alta |
| Nada de cutscenes isoladas, finais ou material de antes do lançamento | Sem filtro de spoiler | Média |
| Audiência brasileira de GTA está no Kick | Kick funciona, mas o modo vigia nunca rodou com live real do Kick | Alta |
| Postar rápido depois do momento | Modo vigia existe, com os erros acima | Média |
| Notas de "viralidade" não preveem desempenho | A nota da IA descarta cortes sozinha abaixo de 5 | Média-baixa |
| Aprender com as métricas reais (nenhum concorrente faz) | Não registra desempenho dos cortes postados | Inferência |
| Filtrar só o jogo certo | Não implementado (item 3 da lista original) | n/a |
| Hashtags que refletem o jogo em tela | Fixas em `#gta6` sem IA | Alta |

O que já está alinhado: início do corte recuado antes do pico de chat, clipes da comunidade como marcador, webcam detectada uma vez por live, cerca de 8 a 12 candidatos por live em fila de revisão, e postagem manual.

## Prioridades recomendadas

### Antes do dia 19 (corrigir o que distorce)

1. Corrigir o modo vigia: cota, salvamento do estado, live que reinicia (itens 1, 5, 8, 9).
2. Reequilibrar a nota: comprimir e limitar o chat, linha de base local de 10 a 15 minutos, bônus quando áudio e chat sobem juntos, peso dos clipes por views absolutas (itens 2, 10).
3. Impedir duplicados e não ressuscitar cortes revisados (item 3).
4. Corrigir a leitura de acentos e emojis (item 4).
5. Tornar a revisão segura contra arquivo aberto, gravação parcial e pedidos de outros sites (itens 6, 7, 13).
6. Blindar a etapa de IA e testá-la com uma chave real (item 14).
7. Testar o modo vigia com uma live real do Kick.

### Logo depois (o que as regras de 2026 exigem)

8. Camada de valor próprio: texto de contexto por corte, campo para comentário seu na tela de revisão (queimado no vídeo), e variação de estilo entre cortes.
9. Música: detectar trechos com música, marcar o risco no corte e travar a versão de Shorts em 60 s quando houver.
10. Filtro de jogo e de spoiler: cortar só quando o jogo em tela for GTA VI e marcar cutscenes para revisão.
11. Hashtags e legendas coerentes com o jogo, mesmo sem IA.

### Depois (diferenciais)

12. Registrar as métricas reais de cada corte postado e usá-las para recalibrar a escolha.
13. Sinais melhores: filtrar o áudio para a faixa da voz, contar risadas e "clipa" no chat, medir o atraso do chat por live.
14. Detecção visual própria de GTA VI (estrelas de procurado, telas de falha), que nenhum concorrente oferece. Só dá para desenhar depois de ver a interface do jogo.
15. Desempenho: codificar uma vez só, renderizar pela placa de vídeo.

## Fora do software, mas decisivo

- **Autorização:** nenhuma política pública de cortes de terceiros foi encontrada para streamers brasileiros. É preciso verificar no Discord de cada um e guardar o registro.
- **Receita:** anúncio de Shorts rende centavos por mil views e a barra de entrada sobe para 20 milhões de views em 90 dias em fevereiro de 2027. O dinheiro do nicho está em campanhas pagas por view.
- **Rockstar:** a política permite gameplay em caráter não comercial; se a monetização por programa de parceria é tolerada não foi verificado. Vale ler a página oficial antes de monetizar.
- **Evidência fraca:** quase todo dado sobre duração, gancho e estilo de legenda vem de fornecedores e não isola cortes de games. Trate como hipótese e meça no próprio canal.
