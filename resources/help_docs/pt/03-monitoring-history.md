# Monitorização e histórico

**Monitorização** = agora, uma execução. **Histórico** = arquivo e estatísticas. O histórico **não** é um segundo painel nem um registo em direto. Iniciar e parar ficam no **cabeçalho**.

## Direto versus arquivo

| | Monitorização | Histórico |
|---|------------|----------|
| Quando | o serviço inicia, corre ou pára | após o fim da execução (e ligação enquanto ainda corre) |
| Grafo | mini-grafo, só leitura, estado dos nós | instantâneo guardado, sem atualização em direto |
| Registo | fluxo, mais recente em cima, pode pausar | linhas fixas, filtráveis |
| Chat | chat da execução, só enquanto corre | transcrição guardada, sem continuar a escrever |

Uma entrada de histórico ainda a correr é só um salto para a Monitorização («Ver em direto»).

## Monitorização sem execução

Sem execução ativa a página mostra a **última execução guardada** para leitura (grafo, atividade, registo, chat). Um aviso diz que nada está em direto. A página fica mesmo vazia só se ainda não houver execução guardada: **Sem execução**, mais a rede ativa ou o aviso de que a seleção rápida está vazia. Desligado / erro / a iniciar / a parar têm textos próprios. Enquanto se indexa conhecimento, o aviso de início passa ao nome desse nó. Os últimos valores podem ficar esbatidos até haver ligação.

## Durante uma execução

Cabeçalho: ID da execução, hora de início, duração, passo aproximado, LLM ativos (local vs nuvem).

**Rede (só leitura):** o mesmo grafo, cores de nó segundo o estado (inativo, à espera, a correr, pronto, erro). Um clique num nó filtra registo/atividade e abre o detalhe (função, estado, espera LLM/ferramenta/entrada/índice, última mensagem, tokens). Sem editar, sem segundo editor.

Se houver conhecimento num agente, o início já mostra a execução durante a indexação: o nó de conhecimento corre com motivo de espera **índice**, o registo nomeia a leitura e os embeddings, e o cabeçalho e o painel mostram o mesmo nome. Um índice já atual é saltado e só anotado como atual.

**Atividade:** nós atuais, progresso «passo x de y», tokens entrada/saída, janela de contexto opcional.

**Recursos do anfitrião:** CPU, RAM, GPU/VRAM **deste PC**, não só da app. Sem GPU local (típico em execuções na nuvem) aparece um aviso, não um erro.

## Chat da rede (monitorização)

Separador **Chat**: conversa do grafo em execução. Só ativo enquanto a execução corre. Sem orquestrador o chat espera a primeira linha e passa-a à cadeia. Com orquestrador falas só com ele. As perguntas ficam abertas na mesma execução. Os textos dos agentes e as ordens internas não aparecem aqui.

Isto **não** é a bolha de ajuda. Histórico e ferramentas são os da rede.

## Registo (monitorização)

Separador **Registo**: linhas com nível (depuração, info, aviso, erro), nó, hora. Mais recente em cima. Pausa pára o acompanhamento; «Ir para os mais recentes» salta outra vez para o fim. Filtros: pesquisa, nível a partir de, um nó, só erros. Exportar as linhas visíveis.

As cargas e as mensagens **mascaram** segredos (por exemplo `Bearer`, prefixos de chave). Não os reenvies sem filtrar.

## Histórico

Faixa: Atualizar, apagar execuções selecionadas, exportar registos, limpar entradas antigas segundo a retenção (ver Definições → Dados, predefinição 90 dias).

**Um filtro** controla tudo: período (hoje, 7/30 dias, de–até), rede, modelo, pesquisa (ID da execução, rede, erro). KPI, gráfico «execuções por dia», erros mais frequentes, separadores Histórico / Por modelo / Por rede e a lista usam o mesmo filtro.

## Resultados de uma execução

| Resultado | Significado |
|----------|-----------|
| Em execução | ainda ativa — no histórico só como ligação |
| Êxito | terminou normalmente |
| Erro | um passo ou o serviço falhou |
| Cancelado | Parar no cabeçalho, janela fechada, ou fim da app (também após um encerramento brusco, no arranque seguinte) |
| Tempo esgotado | limite de tempo |

**Cancelado não é erro.** Tempos esgotados e cancelamentos contam-se à parte nos KPI (rodapé de «Erro»).

## Detalhe da execução

Lado direito ou vista própria: meta, mini-grafo, separadores **Registo**, **Passos**, **Chat**. Passos: nó, função, estado, erro. Chat: transcrição, só leitura. Exportar um único registo.

Apagar entradas do histórico não altera as redes guardadas.
