# Editor e biblioteca

O editor em **Rede** edita **um** documento de grafo. A **Biblioteca** é o catálogo: lista, importar, apagar, ativar. O canvas existe só no editor, não na Biblioteca, Monitorização nem Histórico.

## Dois sítios

| Sítio | Sentido do URL | Ações típicas |
|-----|----------|-------------------|
| Editor | Nova ou uma rede carregada | Desenhar, inspetor, guardar, diálogo Abrir, duplicar, exportar o grafo aberto |
| Biblioteca | todas as redes | Pesquisa, etiquetas, definir como ativa, importar/exportar vários ficheiros, apagar |

**Definir como ativa** e **Apagar** pertencem à biblioteca (ou à seleção rápida para ativa). O diálogo Abrir do editor abre só **uma** rede e não apaga nada.

## Superfície do editor

Em cima a **faixa**: Novo, Guardar, Guardar como, Abrir, Duplicar, Exportar, Validar, Anular/Refazer, Vista (ajustar, grelha, ajuste, mini-mapa), Para a biblioteca.

Centro: **Paleta** (esquerda), **canvas**, **Inspetor** (direita). No ambiente de trabalho podem recolher-se. Em ecrãs estreitos são gavetas. Uma rede vazia só mostra a indicação de arrastar o primeiro nó da paleta para o canvas. As arestas são curvas, como na monitorização e no histórico.

Nós ao arrastar da paleta. Os cartões ficam compactos; os formulários estão no inspetor. Seleção múltipla com Shift ou laço. Delete apaga a seleção. Anular: Ctrl+Z.

Enquanto corre **exactamente esta** rede: faixa **Só de leitura** — primeiro pára no cabeçalho.

## Tipos de nó

| Nome | Tipo | Tarefa |
|-------------|-----|---------|
| Chat | `chat_input` | Conversa da execução. **No máximo um.** Saída **Mensagem**. Com orquestrador o chat fica aberto para perguntas. |
| Orquestrador | `orchestrator` | Voz do chat da execução. Entradas **Mensagem**, **LLM** e **Ferramenta**. Uma saída **Canal** por agente. **Mensagem** só para o **Fim** (ou router). **No máximo um.** |
| LLM | `llm` | Fornecedor (Ollama, xAI, OpenAI, Claude, Gemini), modelo, credencial na nuvem, temperatura, limite de tokens. Saída **LLM**. |
| Agente | `agent` | Prompt de sistema. Entradas Mensagem, LLM, Ferramenta, Conhecimento e **Canal** opcional. Saídas Mensagem e transferência. O canal vem só do orquestrador. Sem canal o agente corre uma vez pela mensagem. |
| Ferramenta | `tool` | First-party: HTTP, pesquisa web, data/hora, calculadora, acesso a ficheiros — ou **MCP**. Saída **Ferramenta**. |
| Conhecimento | `knowledge` | Pasta com ficheiros para a rede. Saída **Conhecimento**, só para o porto Conhecimento do agente. |
| Router | `router` | Bifurca a mensagem segundo condições (primeira linha / ramos com nome) mais saída predefinida. |
| Fim | `end` | Encerramento. **Pelo menos um.** |

## Ligações

Só portos compatíveis:

- Mensagem para Mensagem (Chat → Agente ou Chat → Orquestrador, Agente → Fim, Agente → Router, ramos do router → …). O orquestrador envia Mensagem só para o Fim ou para um router.
- Canal para Canal (Orquestrador → Agente). Um porto por agente. A resposta volta dentro da execução, sem segunda aresta.
- Saída LLM para **LLM** do agente ou do orquestrador — cada agente e o orquestrador precisam de **exactamente uma** aresta destas
- Saída de ferramenta para **Ferramenta** do agente ou do orquestrador (várias permitidas). Uma ferramenta pode ligar-se a ambos.
- Saída de conhecimento só para **Conhecimento** do agente
- Ciclos são proibidos (grafo dirigido sem ciclo)

Um arrasto inválido é recusado.

## Inspetor

Nenhum nó escolhido: nome, descrição, etiquetas, estatísticas, lista de validação da rede **aberta**.

Nó escolhido:

- **LLM:** fornecedor, modelo (lista do runtime), credencial na nuvem, ping, avançado temperatura / máx. tokens. Nuvem sem credencial é inválida.
- **Agente:** prompt de sistema e nome visível. Se o agente está num canal, o inspetor explica que as tarefas vêm do orquestrador.
- **Ferramenta:** tipo. HTTP: método e URL, credencial opcional. Pesquisa web: credencial do tipo pesquisa web. Acesso a ficheiros: pasta raiz, não a raiz da unidade; o agente só trabalha por baixo, e escrever e apagar são interruptores. MCP: servidor ativado nas Definições; predefinição todas as ferramentas desse servidor.
- **Conhecimento:** pasta de origem (escolha de pasta), fornecedor de embeddings (Ollama, OpenAI ou Gemini) e modelo de embeddings, topK, limiar de pontuação, **Reconstruir índice**. A pasta pode estar em qualquer sítio, excepto uma raiz de unidade ou de sistema e o corpus de ajuda. Embeddings na nuvem precisam de credencial. O índice pertence a esta rede, não à ajuda.
- **Chat:** marcador, texto inicial, interruptor «Entrada necessária».
- **Orquestrador:** prompt de sistema. O modelo escolhe uma pergunta, uma tarefa para um agente pelo canal dele, uma resposta ou o fim. Os agentes são os canais, não uma segunda lista. Chama ele próprio as ferramentas ligadas. Só uma pergunta espera pelo utilizador.
- **Router:** ramos com nome (nome + condição) e predefinição.

Os segredos **não** vão para o texto do inspetor nem para a exportação do grafo — só a escolha de uma credencial.

## Validação

**Validar** na faixa verifica, entre outras coisas:

- Nome não vazio
- no máximo um chat, no máximo um orquestrador, pelo menos um fim
- cada agente: exactamente uma aresta LLM. Sem orquestrador, uma mensagem de entrada. Com orquestrador, exactamente um canal e nenhuma cadeia de mensagens no mesmo agente
- LLM: modelo definido; nuvem: credencial
- Ferramenta: tipo; MCP: servidor ativo, caminho raiz se a receita o exigir; acesso a ficheiros: uma pasta que não seja a raiz da unidade
- Conhecimento: caminho definido, não uma raiz, não o corpus de ajuda, credencial de embeddings se o fornecedor a exigir
- sem arestas penduradas, sem ciclos, tipos de porto compatíveis

Válido/Inválido vê-se como distintivo. Redes inválidas podem guardar-se, mas arrancam mal.

## Guardar, abrir, exportar

- **Guardar** (Ctrl+S): a primeira vez diálogo de nome, depois atualização. O URL passa a `/network/…`.
- **Guardar como:** documento novo, torna-se o aberto.
- **Abrir:** uma rede guardada; pesquisa e ordenação. Ações em massa e apagar só na biblioteca.
- **Duplicar:** só com documento já guardado; abre a cópia.
- **Exportar:** transferência do grafo aberto. Contém `credentialId`, sem chaves. A importação na biblioteca descarta segredos anexos.

Sair sem guardar: diálogo Guardar / Descartar / Cancelar.

## Biblioteca

Lista com pesquisa (nome, descrição, etiquetas), ordenação, filtros «só válidas» / «só ativas». Seleção múltipla.

Ações: Novo (editor), Abrir, Duplicar, Mudar o nome, Definir etiquetas, **Definir como ativa** (só uma rede válida), Apagar, Importar, Exportar.

Apagar remove a entrada da área de trabalho, não os teus ficheiros de conhecimento no disco, nem o corpus de ajuda nem as execuções do histórico. Uma rede **em execução** é ignorada. Apagar a rede ativa esvazia a seleção rápida.

Importar: ficheiros com colisão de nome são renomeados ou ignorados. Versões de esquema não suportadas são recusadas.
