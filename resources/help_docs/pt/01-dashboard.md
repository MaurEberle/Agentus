# Painel

A página inicial. Resume configuração, rede ativa e últimas execuções. **Não** é monitorização em direto nem arquivo — há páginas próprias.

## Configuração

O cartão **Configuração** aparece se faltar algo para a primeira execução, por exemplo:

- Ollama inacessível → ligação **Verificar runtime**
- Perfil de ajuda sem fornecedor ou modelo → **Configurar ajuda**
- Ainda sem rede → **Nova rede** ou **Importar rede**

Se o ambiente estiver completo, o cartão desaparece. Modelos opcionais em falta após um setup silencioso sem transferência não são um segundo assistente: o ping do Runtime ou o chat de ajuda mostram o erro.

## Recursos do anfitrião

O mesmo cartão que em **Monitorização**: CPU, memória e GPU/VRAM **deste PC**, não só do processo da app. Os valores atualizam-se em contínuo, mesmo sem execução ativa.

## Estado

Mostra se o serviço está **parado**, **a iniciar**, **em execução** ou **a parar**, mais a rede ativa. Com rede a correr: ligação **Monitorização** e opcionalmente «em execução desde …». Sem seleção rápida: aviso e ligação à **Biblioteca**.

Iniciar e parar ficam no **cabeçalho**, não neste cartão.

## Rede ativa

Nome, número de nós/arestas, Válido/Inválido, última alteração. Ações: **Editar** (editor), **Biblioteca**, **Nova rede**.

Inválido significa: a validação no editor falha (por exemplo modelo em falta num nó LLM). Essas redes não deves iniciar.

## Usados recentemente

Lista curta de redes guardadas pela última utilização. Um clique abre o editor. Vazio: ainda não há redes.

## Últimas execuções

As entradas mais recentes do histórico (êxito, erro, cancelado, tempo esgotado, ou ainda a correr). Uma entrada a correr leva à **Monitorização**, as concluídas ao **Histórico**. Se o store de histórico falhar, aparece um aviso com ligação **Dados**.

## Últimos 7 dias

Estatística breve: número de execuções, com êxito, falhadas. Ligação **Histórico** para filtros e gráficos. É um resumo, não um segundo arquivo.

## Ambiente

- Ollama acessível ou não, número aproximado de modelos
- Problemas de store (definições, ajuda, área de trabalho, histórico)
- **Modo económico**, se a ajuda passou ao modelo de recurso

Ligações: **Dados**, Runtime.

## Acesso rápido

**Nova rede**, **Importar** (biblioteca), **Runtime**. As mesmas ações na navegação e nas Definições.
