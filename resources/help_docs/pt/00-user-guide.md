# Agentus Network — guia rápido

Agentus Network é uma **aplicação de ambiente de trabalho local**. Neste PC constróis redes de agentes, modelos de língua e ferramentas, inicias **uma** execução e vês-la em direto. A interface pertence à própria app (a sua janela), não ao Chrome nem a uma página `file://`.

Ollama é um **serviço à parte**. Fechar ou desinstalar o Agentus Network não pára o Ollama nem apaga modelos.

## Janela e navegação

À esquerda (no telefone: menu hambúrguer):

- **Painel** — início, configuração, rede ativa, últimas execuções
- **Rede** — editor (um grafo)
- **Biblioteca** — todas as redes guardadas
- **Monitorização** — execução em direto
- **Histórico** — execuções terminadas e estatísticas

**Definições** ficam no cabeçalho (engrenagem), não na navegação esquerda.

No cabeçalho também: **Iniciar** / **Parar**, **seleção rápida** da rede ativa, sino (notificações), claro/escuro/sistema, idioma (Deutsch, English, Español, Français, Türkçe, Português, 中文, 日本語, العربية) e botões da janela (minimizar, maximizar, fechar).

Arrasta o logótipo ou o cabeçalho vazio para mover a janela. Iniciar, Parar, a seleção rápida e os botões à direita não são zonas de arrasto.

## Primeiro percurso

1. O Ollama tem de estar a correr (o instalador pode criá-lo e ir buscar os modelos pequenos `nomic-embed-text` e `llama3.2:1b`).
2. Em **Definições → Runtime** verifica a ligação; a lista de modelos não deve estar vazia.
3. Em **Definições → Chat de ajuda** define o fornecedor e o modelo de chat (predefinição: Ollama + `llama3.2:1b`). Os embeddings são **outro** modelo (`nomic-embed-text`).
4. Na **Biblioteca** ou no editor cria uma rede, guarda-a e **ativa-a** na seleção rápida.
5. **Iniciar** no cabeçalho. A execução vê-se em **Monitorização**.

O painel mostra os passos em falta como cartões de configuração.

## Uma rede mínima

No editor (**Rede**) pelo menos:

1. **Entrada de chat** (`chat_input`) — no máximo uma
2. **Agente** — prompt de sistema
3. **LLM** — fornecedor e modelo
4. **Fim** (`end`) — pelo menos um

Ligações (portos tipados, não setas arbitrárias):

- Entrada de chat **Mensagem** → Agente **Mensagem**
- LLM **LLM** → Agente **LLM**
- Agente **Mensagem** → Fim

Opcional: **Ferramenta** para o porto **Ferramenta** do agente, **Conhecimento** para **Conhecimento**. Guardar. Na **Biblioteca**, «Definir como ativa» se a seleção rápida ainda não o for.

## Iniciar e parar

**Iniciar** lança **uma** execução da rede **ativa** (seleção rápida). Nunca corre uma segunda rede em paralelo. Um segundo início é recusado até **Parar**.

**Parar** cancela a execução (resultado **Cancelado**, não **Erro**). O Ollama continua ligado.

Sem rede ativa não arranca nada. Uma rede inválida (erro de validação, modelo em falta) deve ser verificada no editor antes de iniciar.

Enquanto a rede ativa corre, **esse** documento no editor é só de leitura. Podes continuar a ver outras redes; apagar a rede em execução na biblioteca está bloqueado.

Fechar a janela termina a execução e a app. O Ollama continua.

## O chat de ajuda não é o chat da rede

Em baixo à direita: bolha = **ajuda da app** (este guia, termos do grafo, pesquisa web opcional). O onboarding explica-o na primeira abertura.

Em **Monitorização**, o separador **Chat** = **chat da execução** do grafo (nó entrada de chat). Fala com a rede de agentes.

Não partilham **histórico**, ferramentas nem credenciais. A ajuda **não** usa servidores MCP.

## Ollama e a nuvem

- **Local:** Ollama, nas Definições como Runtime. Lá listas e testas modelos. A app **não** descarrega modelos em silêncio em tempo de execução.
- **Nuvem:** credenciais em **Definições → Credenciais** (xAI, compatível com OpenAI, pesquisa web, …). As listas mostram só uma **máscara**, nunca o segredo. Os nós LLM e a ajuda apontam para a credencial pelo nome, não com a chave no grafo.

Compatível com OpenAI (por exemplo um servidor local) precisa da URL de base em **Runtime** e muitas vezes de uma credencial.

## Uma instância

Um segundo arranque traz a janela existente para a frente. Não há segundo backend nem segunda execução.

## Portátil e instalada

A app instalada guarda dados na pasta local **Agentus-Network**, não junto do programa. A variante portátil (ficheiro `portable.txt` junto do EXE) guarda dados **junto do EXE**. Em Portable tens de trazer tu o WebView2 e o Ollama.
