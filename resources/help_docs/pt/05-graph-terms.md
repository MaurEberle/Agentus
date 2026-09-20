# Termos

Glossário breve para o chat de ajuda e o editor.

## Grafo / rede

Documento guardado de nós e arestas. Editas-no no editor e geres cópias na biblioteca. A rede **ativa** é a da seleção rápida — só essa arranca com **Iniciar**.

## Execução (run)

Uma passagem do grafo ativo. Corre no máximo **uma**. Iniciar e parar no cabeçalho. Resultados: a correr, êxito, erro, cancelado, tempo esgotado.

## Nós e arestas

Peças (entrada de chat, agente, LLM, ferramenta, conhecimento, router, fim) e ligações tipadas. Setas arbitrárias entre caixas são inválidas.

## Agente

Nó com prompt de sistema. Modelo, mensagem, ferramentas e conhecimento chegam por portos, não como chaves embutidas.

## Nó LLM

Escolhe fornecedor e modelo. Local via Ollama, senão nuvem ou URL compatível com OpenAI mais credencial.

## Entrada de chat

Única entrada de texto do utilizador na execução. No máximo uma por rede. O chat de monitorização escreve aqui.

## Ferramenta

First-party (HTTP, pesquisa web, data/hora, calculadora) ou MCP. Configuração no inspetor, execução só no run.

## Conhecimento (rede)

Nó knowledge: pasta **sob** a pasta de dados da app. Índice próprio, topK e pontuação. **Não** é o corpus de ajuda. Não é a raiz da unidade.

## Ajuda-RAG

Documentos na pasta de ajuda da pasta de dados (guias predefinidos mais os teus Markdown). Só o chatbot de ajuda. Após alterações, reconstrói o índice em Definições → Chat de ajuda.

## Credencial

Chave guardada no cofre do Windows. Nas listas só máscara. No grafo só o ID/escolha, nunca o segredo. A exportação não contém palavras-passe.

## MCP

Model Context Protocol: servidores de ferramentas externos. Cria-os e ativa-os nas Definições, liga-os no grafo como nó de ferramenta do tipo MCP. A ajuda não usa MCP.

## Fornecedor

`ollama` (local), `xai`, `openai`, `anthropic` (Claude), `gemini` (nuvem, primeiro a chave API, depois a lista de modelos), `openai_compat` (API HTTP compatível própria, p. ex. LM Studio).

## Ollama

Serviço separado para modelos locais. A app é o cliente. O setup pode criar o Ollama e dois modelos pequenos por omissão. Fechar a app deixa o Ollama a correr.

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
