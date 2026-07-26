# Especificação de Requisitos

## 1. Requisitos Funcionais (RF)
| ID | Título | Descrição | Prioridade |
| :--- | :--- | :--- | :--- |
| RF001 | Importar Dados por CSV | Permitir que o gestor importe arquivos CSV de grades, salas, restrições e alocações. | Essencial |
| RF002 | Visualizar Dashboard | Exibir painel consolidado da ocupação, bloqueios e conflitos das salas. | Essencial |
| RF003 | Consultar Grades | Exibir a demanda de atendimento filtrada por especialidade, dia e turno. | Essencial |
| RF004 | Consultar Salas | Listar todas as salas com características, status e restrições. | Essencial |
| RF005 | Verificar Conflitos | Sistema deve identificar e alertar incompatibilidades automaticamente. | Essencial |
| RF006 | Editar Alocação | Alteração manual assistido de sala associada à grade. | Essencial |
| RF007 | Consultar Detalhes de uma Sala | Exibir informações completas de status, localização e conflitos de uma sala. | Essencial |
| RF008 | Registrar Histórico de ajustes | Salvar registro automático de toda alteração manual e seus motivos. | Essencial |
| RF009 | Justificar Ajustes com Conflito | Permitir a confirmação de um ajuste com alerta mediante registro de justificativa. | Média |
| RF010 | Exportar Distribuição Consolidada | Obter visão estruturada da distribuição para consulta e futura exportação em PDF ou CSV. | Baixa |

## 2. Requisitos Não Funcionais (RNF)
| ID | Categoria | Descrição |
| :--- | :--- | :--- |
| RNF001 | Arquitetura de Tecnologia | O frontend deve utilizar Vue 3 e Tailwind CSS, e o backend deve utilizar FastAPI. |
| RNF002 | Segurança | Utilizar autenticação já existente com JWT para rotas sensíveis. |
| RNF003 | Estrutura | Padrão obrigatório: Frontend -> Router -> Controller -> Provider -> SQL Template. |
| RNF004 | Tratamento de Falhas | Retornar erro claro ao usuário técnico se o arquivo CSV for malformado ou ausente. |
| RNF005 | Integridade de Dados | O sistema deve registrar erros e impedir falhas silenciosas quando houver campos obrigatórios ausentes. |
| RNF006 | Armazenamento| Banco de dados local para configurações, restrições e histórico de uso. |

## 3. Detalhamento SDD (CARE)
### [CARE-RF001] Importar Dados por CSV
* **Context (Contexto)**: O MVP utiliza arquivos CSV locais (grades, salas, restrições e alocações) como origem de dados.
* **Action (Ação)**: O usuário seleciona o tipo de arquivo e faz o upload, para que o sistema valide as colunas obrigatórias.
* **Result (Resultado)**: Os dados válidos são importados, informando a conclusão e atualizando o dashboard operacional.
* **Evaluation (Avaliação)**: Deve rejeitar arquivos sem colunas obrigatórias ou vazios informando o motivo, e carregar corretamente os registros válidos.

### [CARE-RF002] Visualizar Dashboard Operacional
* Context (Contexto): Necessidade de centralizar a visualização operacional e organizar as informações de grades e salas.
* Action (Ação): O gestor acessa o dashboard e seleciona os filtros desejados de dia da semana, turno, especialidade, bloco ou status.
* Result (Resultado): O sistema atualiza os cards de resumo, a tabela de ocupação e o grid visual de salas utilizando códigos de cores (verde, azul, amarelo, cinza, vermelho).
* Evaluation (Avaliação): O sistema deve exibir status visual claro para as salas, atualizar indicadores ao alterar filtros e destacar os conflitos encontrados.

### [CARE-RF005] Verificar Conflitos Automaticamente
* Context (Contexto): Identificar inconsistências causadas pela relação complexa de ensino, especialidades e infraestrutura.
* Action (Ação): O sistema cruza os dados de grades, salas, restrições e alocações de forma automática, aplicando regras de negócio e identificando choques.
* Result (Resultado): Os conflitos são classificados por gravidade (ex: alerta ou conflito crítico) e exibidos no dashboard e nos detalhes da sala.
* Evaluation (Avaliação): A verificação deve ocorrer sem intervenção manual, cada conflito deve conter tipo, gravidade e descrição, e os conflitos devem ser recalculados caso haja ajuste.

### [CARE-RF006] Editar Alocação de Sala
* Context (Contexto): O processo exige tomada de decisão humana para resolver inconsistências e adaptar as necessidades qualitativas das clínicas.
* Action (Ação): Via endpoint `POST /api/alocacoes/ajustar` fornecendo `id_alocacao` e `novo_id_sala`, o gestor seleciona a nova sala e o sistema verifica possíveis novos conflitos antes de prosseguir.
* Result (Resultado): A associação da grade com a sala é atualizada, recalcula-se os alertas e a alteração é armazenada no histórico de ajustes.
* Evaluation (Avaliação): Impedir a seleção de salas inexistentes ou bloqueadas sem alertas críticos e registrar detalhadamente o ajuste realizado no histórico.

### [CARE-RF008] Registrar Histórico de Ajustes
* Context (Contexto): Necessidade de rastrear todas as alterações manuais feitas pela chefia na distribuição planejada para auditoria ou acompanhamento.
* Action (Ação): O sistema intercepta cada operação de ajuste de alocação de sala.
* Result (Resultado): Salva um registro contendo o ID da alocação, a sala anterior, a nova sala, data, hora, usuário, os conflitos do momento e a justificativa (se fornecida).
* Evaluation (Avaliação): Garantir que todo ajuste gere o registro, permitir a consulta futura do histórico e rastrear o usuário responsável.