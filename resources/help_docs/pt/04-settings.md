# Definições

Engrenagem no cabeçalho. Secções à esquerda: Aparência, Credenciais, Runtime, Chat de ajuda, Servidores MCP, Dados, Acerca de. Campos por guardar ao mudar: diálogo Ficar / Descartar.

## Aparência

Claro, escuro ou sistema — vale para toda a app, incluindo o cabeçalho. **Idioma** é uma lista pendente com bandeira: Deutsch, English, Español, Français, Türkçe, Português, 中文, 日本語, العربية. O nome entre parênteses é a tradução no idioma da interface atual.

Interruptor **Botão de ajuda**: mostra ou esconde a bolha em baixo à direita. A **configuração** do chatbot fica em **Chat de ajuda**, mesmo com a bolha escondida.

## Credenciais

Segredos com nome para modelos na nuvem, pesquisa web e algumas receitas MCP. Criar: nome, tipo, segredo **uma vez**. Depois só a **máscara**. Editar pode substituir o segredo (vazio = inalterado).

Tipos entre outros: xAI, compatível com OpenAI, pesquisa web, GitHub, Azure, GitLab, Slack, Notion, Atlassian, Linear, Postgres, token.

**Apagar** está bloqueado enquanto o perfil de ajuda, uma rede (LLM/ferramenta) ou um servidor MCP usarem a credencial. Primeiro remove a associação.

## Runtime

**URL de base do Ollama** (costuma ser o endereço local do Ollama) e opcionalmente **URL de base compatível com OpenAI**. **Verificar ligação** e a **lista de modelos** passam pela app, não pelo browser.

Sem Ollama acessível, os nós LLM locais e a ajuda predefinida ficam parados. Instalas modelos com o Ollama ou no setup; a app **não** faz pull em silêncio em tempo de execução.

## Chat de ajuda

Único sítio para o widget de ajuda. Incompleto sem fornecedor e modelo de chat.

- Fornecedor e modelo de chat (predefinição Ollama / `llama3.2:1b`)
- credencial na nuvem opcional
- **Fornecedor e modelo de embeddings** (predefinição Ollama / `nomic-embed-text`) — **não** é o modelo de chat
- modelo económico opcional (recurso, predefinição o mesmo chat pequeno)
- pesquisa web sim/não mais credencial de pesquisa; sem credencial o chat continua configurado e a pesquisa desligada
- verificar ligação, limpar histórico, **reconstruir índice**, voltar a mostrar o onboarding

Depois de mudar o modelo de embeddings ou de novos ficheiros no corpus de ajuda: **reconstruir índice**. O corpus é a pasta de documentos de ajuda na pasta de dados, não o conhecimento da rede.

A ajuda **não** usa servidores MCP nem o knowledge dos grafos.

## Servidores MCP

Modelos (**receitas**) para ferramentas externas: GitHub, sistema de ficheiros, Git, Playwright, Postgres, Slack, Notion, formatos Office e outras. As receitas não são programas incluídos. Muitas precisam de Node/`npx`, Docker ou `uvx` no PC mais uma credencial.

Predefinição: servidor **inativo**. A app não arranca processos MCP ao abrir, mas quando uma execução precisa de um nó de ferramenta MCP ligado.

Criar a partir de uma receita (credencial, caminho raiz opcional) ou como **servidor próprio** (comando, argumentos ou URL). Usa comandos desconhecidos só se confiares neles. A sonda verifica se responde; «Falta o runtime» se não houver Node/Docker/`uvx`.

O Office agrupa PDF e formatos Office; ativa os presets soltos só se realmente precisares.

Apagar remove a configuração do servidor, não o Ollama nem as credenciais.

## Dados

Mostra a **pasta de dados** e o estado dos stores: Definições, Ajuda, Área de trabalho, Histórico — sem vista SQL e sem segredos.

**Mudar** de pasta só se nenhuma rede inicia, corre ou pára. Raízes de unidade ou de sistema são inválidas. Opcional copiar o conteúdo para a pasta nova; a antiga fica.

**Portátil** ou uma pasta imposta do exterior: caminho **só de leitura**.

**Retenção do histórico:** 30 / 90 / 365 dias ou ilimitado (predefinição 90). A página de histórico pode limpar entradas antigas em conformidade.

## Acerca de

Versão da UI e da API, estado aproximado do Ollama, se os stores respondem. Sem segredos nem caminhos internos com nome de utilizador numa superfície que partilhas.
