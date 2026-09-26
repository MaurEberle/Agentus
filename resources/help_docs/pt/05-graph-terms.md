# Termos

Glossário breve para o chat de ajuda e o editor.

## Grafo / rede

Documento guardado de nós e arestas. Editas-no no editor e geres cópias na biblioteca. A rede **ativa** é a da seleção rápida — só essa arranca com **Iniciar**.

## Execução (run)

Uma passagem do grafo ativo. Corre no máximo **uma**. Iniciar e parar no cabeçalho. Resultados: a correr, êxito, erro, cancelado, tempo esgotado.

## Nós e arestas

Peças (chat, orquestrador, agente, LLM, ferramenta, conhecimento, router, fim) e ligações tipadas. Setas arbitrárias entre caixas são inválidas.

## Agente

Nó com prompt de sistema. Modelo, mensagem, ferramentas e conhecimento chegam por portos. Sem orquestrador a mensagem inicia-o, e mensagem ou transferência seguem com a resposta. Com orquestrador fica no seu próprio canal: uma tarefa entra, um resultado volta.

## Nó LLM

Escolhe fornecedor e modelo. Local via Ollama; senão, nuvem mais credencial.

## Chat

Única entrada de texto do utilizador na execução. No máximo um por rede. O chat de monitorização escreve aqui. Com orquestrador a conversa fica aberta em várias mensagens.

## Orquestrador

Nó com o seu próprio LLM. É a única voz do chat da execução, faz perguntas e chama os agentes ligados um de cada vez, cada um por um canal. No máximo um. O chat só se liga a ele. A saída de mensagem vai para o Fim ou para um router. Não vês os textos dos agentes nem as ordens internas como bolhas. A app junta o último resultado à tarefa seguinte. Um agente está no canal ou na cadeia de mensagens. As ferramentas podem ligar-se ao seu porto Ferramenta. Ele próprio as chama.

## Ferramenta

First-party (HTTP, pesquisa web, data/hora, calculadora, acesso a ficheiros) ou MCP. O acesso a ficheiros fica numa pasta raiz, não na raiz da unidade. Configuração no inspetor, execução só durante o run.

## Conhecimento (rede)

Nó de conhecimento: uma pasta de textos para a rede. Pode estar em qualquer sítio, excepto uma raiz de unidade ou de sistema e o corpus de ajuda. Modelo de embeddings próprio, índice, topK e pontuação. **Não** é o corpus de ajuda. Ao iniciar vês a indexação; um índice já atual é saltado.

## Ajuda-RAG

Documentos na pasta de ajuda da pasta de dados (guias predefinidos mais os teus Markdown). Só o chatbot de ajuda. Após alterações, reconstrói o índice em Definições → Chat de ajuda.

## Credencial

Chave guardada no cofre do Windows. Nas listas só máscara. No grafo só o ID/escolha, nunca o segredo. A exportação não contém palavras-passe.

## MCP

Model Context Protocol: servidores de ferramentas externos. Cria-os e ativa-os nas Definições, liga-os no grafo como nó de ferramenta do tipo MCP. A ajuda não usa MCP.

## Fornecedor

Na lista: `ollama` (local), `xai`, `openai`, `anthropic` (Claude), `gemini` (nuvem: primeiro a credencial, depois a lista de modelos). Embeddings: Ollama, OpenAI, Gemini. `openai_compat` continua válido em grafos e credenciais antigos, mas já não está na lista de modelos.

## Ollama

Serviço separado para modelos locais. A app é o cliente. Se está instalado, o endereço é local e a porta não responde, a app inicia-o e não o pára. O setup pode criar o Ollama, esperar um momento e carregar dois modelos pequenos por omissão se ele responder.

## Painel, monitorização, histórico

Painel = resumo e configuração. Monitorização = direto. Histórico = arquivo. Não é a mesma página três vezes.

## Válido / inválido

Validação do grafo. Inválido pode guardar-se, mas não serve para iniciar. Só uma rede válida se pode definir como ativa.

## Seleção rápida

Escolha no cabeçalho da rede ativa. Equivale a «Definir como ativa» na biblioteca.

## Modo económico

A ajuda passa ao modelo de recurso se o principal não responder. O painel pode mostrá-lo em Ambiente.

## Portátil

`portable.txt` junto do EXE: dados junto da aplicação. Cópia instalada: dados na pasta da app, programas à parte.
