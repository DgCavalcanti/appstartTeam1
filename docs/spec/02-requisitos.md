# Especificação de Requisitos

## 1. Requisitos Funcionais (RF)
| ID | Título | Descrição | Prioridade |
| :--- | :--- | :--- | :--- |
| RF001 | Importar e tratar a grade do AGHU | Importar a grade exportada (.csv/.xlsx) e aplicar o pipeline de tratamento: filtros, deduplicação e agregação, reduzindo os dados a contagens por unidade/dia/turno. | Essencial |
| RF002 | Validar e ajustar grades | Exibir a demanda por unidade em cada dia/turno como planilha editável e permitir corrigir valores e escolher quais unidades participam. | Essencial |
| RF003 | Manter o panorama de salas | Editar, por pavimento, a quantidade de salas de cada tipo; a capacidade em estações é derivada, nunca digitada. | Essencial |
| RF004 | Definir obrigatoriedades e preferências | Associar uma clínica a um pavimento como obrigatória (trava rígida) ou preferencial (afinidade flexível). | Essencial |
| RF005 | Executar a alocação automática | Rodar o motor que aloca cada clínica inteira em um pavimento para a semana, respeitando a capacidade por turno e as restrições. | Essencial |
| RF006 | Ajustar o resultado manualmente | Editar quantas grades cada clínica atende por turno, redistribuindo a "não alocação" dentro do pavimento sem refazer todo o processo. | Essencial |
| RF007 | Guardar e comparar cenários | Persistir cada alocação como um cenário autocontido, listar o histórico, clonar um cenário e excluir. | Essencial |
| RF008 | Visualizar o painel consolidado | Exibir, somente leitura, indicadores gerais, ocupação por turno e por pavimento (em salas físicas) e a distribuição das clínicas, com filtros por bloco e pavimento. | Essencial |
| RF009 | Reconciliar novidades da importação | Sinalizar unidades ou condições nunca vistas antes e destacar profissionais que atendem em duas clínicas no mesmo turno para revisão. | Média |
| RF010 | Controlar o avanço das etapas | Rastrear o status de cada uma das 6 etapas e marcar a alocação como desatualizada quando um insumo anterior muda. | Essencial |

## 2. Requisitos Não Funcionais (RNF)
| ID | Categoria | Descrição |
| :--- | :--- | :--- |
| RNF001 | Arquitetura de Tecnologia | Frontend em Vue 3 + TypeScript + Tailwind CSS; backend em Python + FastAPI. |
| RNF002 | Uso local | Aplicação de uso local por um único gestor, sem autenticação e sem controle de concorrência. |
| RNF003 | Camadas | Fluxo unidirecional API → Serviço → Domínio → Repositório; cada camada só conhece a de baixo. |
| RNF004 | Domínio isolado | As regras de negócio (tratamento da importação e motor de alocação) ficam em Python puro, testáveis sem subir a aplicação nem o banco. |
| RNF005 | Persistência | Banco SQLite em arquivo único, com esquema versionado por Alembic; sem configuração externa. |
| RNF006 | Tratamento de falhas | Retornar erro claro ao gestor quando o arquivo do AGHU estiver ausente, vazio ou malformado, sem falhas silenciosas. |
| RNF007 | Cenário autocontido | Cada alocação guarda a própria cópia dos insumos (grades, salas, restrições, resultado); reabrir um cenário mostra exatamente o que o gerou. |
| RNF008 | Dado tratado na entrada | Filtragem, deduplicação e agregação acontecem na importação; as linhas brutas do AGHU não são persistidas. |

## 3. Detalhamento SDD (CARE)

### [CARE-RF001] Importar e tratar a grade do AGHU
* **Context**: A origem dos dados é a grade exportada do AGHU (.csv/.xlsx), volumosa e com colunas que não entram na alocação.
* **Action**: O gestor envia o arquivo; o sistema aplica o pipeline — filtra situação, condição, unidades que não participam, sábado e turno Noite; deduplica por (profissional, unidade, dia, turno) e deriva as contagens.
* **Result**: Uma demanda limpa e compacta (grade_slot + grade_demanda) e um relatório da redução (bruto → filtrado → slots → demandas). As linhas brutas não persistem.
* **Evaluation**: Rejeita arquivo ausente/vazio/malformado com mensagem clara; registra quantos slots saíram por cada motivo; a soma das demandas deve bater com o total de slots.

### [CARE-RF005] Executar a alocação automática
* **Context**: Cada clínica é um vetor de 10 demandas (5 dias × 2 turnos) e cada pavimento é uma caixa cuja capacidade em estações vale nos 10 turnos.
* **Action**: O motor fixa as obrigatórias, ordena as demais pelo pico, faz colocação gulosa (cabe inteira → maior afinidade; senão → menor estouro), aplica passada de melhoria (move/swap) e reparte a sobra proporcionalmente.
* **Result**: Cada clínica recebe um pavimento para a semana; por unidade/dia/turno, o número de grades alocadas e não alocadas, mais indicadores de ocupação.
* **Evaluation**: Havendo capacidade, zero grades não alocadas; só a obrigatoriedade gera sobra; a preferência nunca faz uma clínica perder atendimento havendo espaço ao lado; a mesma entrada produz sempre a mesma saída.

### [CARE-RF006] Ajustar o resultado manualmente
* **Context**: O gestor pode discordar da divisão automática da sobra em um turno.
* **Action**: Na etapa 6, edita quantas grades uma clínica atende naquele turno; o restante da demanda vira "não alocação".
* **Result**: O resultado da etapa 5 é alterado diretamente, sem refazer o processo; a etapa 5 continua válida.
* **Evaluation**: Não permite alocar mais que a demanda do turno nem estourar a capacidade do pavimento; o ajuste é acessível a qualquer momento após a execução.

### [CARE-RF010] Controlar o avanço das etapas
* **Context**: O fluxo é sequencial, mas o gestor pode voltar a qualquer etapa e ver o panorama atualizado.
* **Action**: Cada etapa carrega um status (pendente, preenchida, desatualizada); mexer nas grades (1–2), no panorama (3) ou nas restrições (4) marca a alocação (5–6) como desatualizada.
* **Result**: O sistema avisa em vez de apagar — o gestor decide se refaz a execução.
* **Evaluation**: Alterar um insumo anterior à alocação sempre a marca como desatualizada, preservando o resultado anterior no banco.
