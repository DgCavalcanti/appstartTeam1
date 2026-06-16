# Documento de Casos de Uso — Sistema de Apoio à Alocação Ambulatorial (SAA)

## 1. Introdução

Este documento descreve os principais casos de uso do Sistema de Apoio à Alocação Ambulatorial (SAA), com base nas funcionalidades efetivamente implementadas. Cada caso de uso apresenta ator(es), pré-condições, fluxo principal, fluxos alternativos e pós-condições.

## 2. Atores

| Ator | Descrição |
|---|---|
| Usuário | Pessoa autenticada via Active Directory institucional que opera as funcionalidades do SAA. |
| Administrador | Usuário autenticado com privilégio adicional, com acesso à área de Administração. |
| Sistema AGHU | Sistema externo de origem dos dados reais de grades e consultas, integrado por meio de arquivos CSV exportados e importados manualmente. |

## 3. Lista de Casos de Uso

| ID | Nome | Ator Principal |
|---|---|---|
| UC01 | Autenticar no Sistema (Login) | Usuário |
| UC02 | Visualizar Painel SAA | Usuário |
| UC03 | Listar e Filtrar Grades AGHU | Usuário |
| UC04 | Listar e Filtrar Salas | Usuário |
| UC05 | Listar Restrições de Sala | Usuário |
| UC06 | Listar e Filtrar Alocações | Usuário |
| UC07 | Ajustar Alocação Manualmente | Usuário |
| UC08 | Consultar Histórico de Ajustes | Usuário |
| UC09 | Importar Dados via CSV | Usuário |
| UC10 | Visualizar Capacidade Ambulatorial (AGHU) | Usuário |
| UC11 | Visualizar e Filtrar Consultas AGHU | Usuário |
| UC12 | Visualizar Qualidade dos Dados | Usuário |
| UC13 | Acessar Área de Administração | Administrador |
| UC14 | Encerrar Sessão (Logout) | Usuário |

## 4. Especificação dos Casos de Uso

### UC01 — Autenticar no Sistema (Login)

**Ator(es):** Usuário

**Pré-condições:** Usuário possui credenciais válidas no Active Directory institucional (domínio EBSERHNET).

**Fluxo Principal**
1. Usuário acessa a tela de Login.
2. Informa o usuário (formato `DOMINIO\usuario`) e a senha.
3. Opcionalmente marca a opção "Lembrar de mim".
4. Sistema valida as credenciais junto ao Active Directory.
5. Sistema emite um token de acesso JWT.
6. Se "Lembrar de mim" estiver marcado, o sistema também emite um cookie HttpOnly de refresh token.
7. Usuário é redirecionado à área autenticada do sistema.

**Fluxos Alternativos / Exceções**
- Credenciais inválidas: o sistema exibe mensagem de erro e mantém o usuário na tela de login.
- Token de acesso expirado: se houver refresh token válido, o sistema emite um novo token de acesso automaticamente.

**Pós-condições:** Usuário autenticado; token de acesso disponível para as próximas requisições.

### UC02 — Visualizar Painel SAA

**Ator(es):** Usuário

**Pré-condições:** Usuário autenticado; dados de grades, salas, restrições e alocações previamente importados.

**Fluxo Principal**
1. Usuário acessa o item "Painel" no menu lateral.
2. Sistema calcula os indicadores gerais (total de salas, disponíveis, bloqueadas, em reforma/manutenção, grades no filtro, conflitos críticos).
3. Sistema exibe a grade visual de salas (com cores indicando status e conflitos) e a tabela de ocupação por grade.
4. Usuário aplica filtros opcionais (dia da semana, turno, bloco, status da sala).
5. Sistema recalcula indicadores, grade visual e lista de conflitos conforme o filtro aplicado.
6. Usuário pode clicar em uma sala para visualizar seus detalhes em uma janela modal.

**Fluxos Alternativos / Exceções**
- Nenhum dado importado: sistema exibe mensagem orientando a importação via CSV.

**Pós-condições:** Indicadores, grade visual e lista de conflitos exibidos de acordo com os filtros selecionados.

### UC03 — Listar e Filtrar Grades AGHU

**Ator(es):** Usuário

**Pré-condições:** Arquivo de grades AGHU previamente importado.

**Fluxo Principal**
1. Usuário acessa o item "Grades" no menu lateral.
2. Sistema exibe a lista de grades (até 5.000 registros por consulta).
3. Usuário aplica filtros por especialidade, turno, dia da semana e/ou situação da grade.
4. Sistema retorna a lista filtrada e o resumo agregado correspondente.

**Pós-condições:** Lista de grades exibida conforme os filtros aplicados.

### UC04 — Listar e Filtrar Salas

**Ator(es):** Usuário

**Pré-condições:** Cadastro de salas previamente importado.

**Fluxo Principal**
1. Usuário acessa o item "Salas" no menu lateral.
2. Sistema exibe a lista de salas cadastradas.
3. Usuário aplica filtros por bloco, status e/ou especialidade preferencial.
4. Usuário pode selecionar uma sala específica para visualizar seus detalhes completos.

**Pós-condições:** Lista (ou detalhe) de salas exibida conforme os filtros aplicados.

### UC05 — Listar Restrições de Sala

**Ator(es):** Usuário

**Pré-condições:** Arquivo de restrições previamente importado.

**Fluxo Principal**
1. Usuário acessa a listagem de restrições.
2. Sistema exibe todas as restrições cadastradas (tipo equipamento obrigatório ou especialidade exclusiva) e a sala associada a cada uma.

**Pós-condições:** Lista completa de restrições exibida.

### UC06 — Listar e Filtrar Alocações

**Ator(es):** Usuário

**Pré-condições:** Arquivo de alocações previamente importado.

**Fluxo Principal**
1. Usuário acessa o item "Alocações" no menu lateral.
2. Sistema exibe a lista de alocações vigentes (grade vinculada a sala, dia e turno).
3. Sistema sinaliza as alocações que possuem conflitos associados.

**Pós-condições:** Lista de alocações exibida, com indicação de conflitos quando existentes.

### UC07 — Ajustar Alocação Manualmente

**Ator(es):** Usuário

**Pré-condições:** Alocação existente selecionada; sala de destino cadastrada.

**Fluxo Principal**
1. Usuário seleciona uma alocação na tela "Alocações".
2. Usuário escolhe a nova sala de destino para essa alocação.
3. Sistema simula os conflitos da situação atual (antes) e da situação proposta (depois, com a nova sala).
4. Sistema exibe ao usuário os conflitos resultantes da simulação, com suas gravidades.
5. Se a simulação indicar ao menos um conflito de gravidade crítica ou operacional, o sistema exige uma justificativa textual.
6. Usuário informa a justificativa (quando exigida) e confirma o ajuste.
7. Sistema persiste a nova alocação e registra o histórico do ajuste (usuário, data/hora, sala anterior, sala nova, justificativa e conflitos antes/depois).

**Fluxos Alternativos / Exceções**
- Conflito relevante sem justificativa informada: sistema bloqueia a confirmação e solicita a justificativa.
- Alocação ou sala de destino inexistente: sistema rejeita a operação com erro.

**Pós-condições:** Alocação atualizada com a nova sala; novo registro de histórico criado.

### UC08 — Consultar Histórico de Ajustes

**Ator(es):** Usuário

**Pré-condições:** Existência de ao menos um ajuste de alocação realizado anteriormente.

**Fluxo Principal**
1. Usuário acessa o item "Histórico" no menu lateral.
2. Sistema exibe a lista de ajustes realizados, incluindo usuário responsável, data/hora, sala anterior, sala nova, justificativa e conflitos antes/depois de cada ajuste.

**Pós-condições:** Histórico de ajustes exibido em ordem cronológica.

### UC09 — Importar Dados via CSV

**Ator(es):** Usuário

**Pré-condições:** Arquivo CSV disponível no formato esperado para o tipo de dado (Grades AGHU, Consultas AGHU, Salas, Restrições ou Alocações).

**Fluxo Principal**
1. Usuário acessa a tela "Importar CSV".
2. Usuário seleciona o arquivo correspondente ao tipo de dado desejado, no cartão específico.
3. Sistema valida o formato do arquivo (para Grades AGHU, valida adicionalmente o layout do cabeçalho).
4. Sistema realiza backup do arquivo anteriormente carregado, salvando uma cópia com data/hora na pasta de importados, antes de sobrescrevê-lo.
5. Sistema processa o novo arquivo, atualiza os dados e recalcula indicadores e conflitos.
6. Sistema exibe o resultado da importação (linhas lidas, linhas válidas, registros únicos e eventuais avisos).

**Fluxos Alternativos / Exceções**
- Formato de cabeçalho inválido (Grades AGHU): sistema rejeita a importação com erro de validação.
- Linhas inválidas dentro de um arquivo válido: são reportadas como avisos, sem impedir a importação das linhas válidas restantes.

**Pós-condições:** Dados atualizados no sistema; indicadores e conflitos recalculados; backup do arquivo anterior preservado.

### UC10 — Visualizar Capacidade Ambulatorial (AGHU)

**Ator(es):** Usuário

**Pré-condições:** Dados de grades e/ou consultas AGHU previamente importados.

**Fluxo Principal**
1. Usuário acessa o item "Capacidade" no menu lateral.
2. Sistema apresenta o resumo agregado de capacidade ambulatorial calculado a partir dos dados reais do AGHU.

**Pós-condições:** Resumo de capacidade exibido.

### UC11 — Visualizar e Filtrar Consultas AGHU

**Ator(es):** Usuário

**Pré-condições:** Arquivo de consultas AGHU previamente importado.

**Fluxo Principal**
1. Usuário acessa o item "Consultas" no menu lateral.
2. Usuário aplica filtros por especialidade, unidade funcional, profissional, turno, dia da semana, situação da consulta e/ou apenas excedentes.
3. Sistema retorna a lista filtrada (até 1.000 registros) e os resumos agregados por especialidade e por dia/turno.

**Pós-condições:** Lista e resumos de consultas exibidos conforme os filtros aplicados.

### UC12 — Visualizar Qualidade dos Dados

**Ator(es):** Usuário

**Pré-condições:** Dados do AGHU previamente importados.

**Fluxo Principal**
1. Usuário acessa o item "Qualidade" no menu lateral.
2. Sistema apresenta o relatório de qualidade dos dados, listando os problemas identificados nos arquivos importados.

**Pós-condições:** Relatório de qualidade de dados exibido.

### UC13 — Acessar Área de Administração

**Ator(es):** Administrador

**Pré-condições:** Usuário autenticado com privilégio de administrador.

**Fluxo Principal**
1. Usuário acessa o item "Administração" no menu lateral (visível apenas a administradores).
2. Sistema exibe as informações do usuário obtidas do Active Directory.

**Fluxos Alternativos / Exceções**
- Usuário autenticado sem privilégio de administrador: sistema exibe a mensagem "Acesso Negado".

**Pós-condições:** Informações de administração exibidas (ou acesso negado, conforme o privilégio do usuário).

### UC14 — Encerrar Sessão (Logout)

**Ator(es):** Usuário

**Pré-condições:** Usuário autenticado.

**Fluxo Principal**
1. Usuário aciona a opção de logout no menu de perfil.
2. Sistema invalida o refresh token associado (quando existente) e remove o cookie correspondente.
3. Usuário é redirecionado à tela de login.

**Pós-condições:** Sessão do usuário encerrada; token de acesso e refresh token invalidados.
