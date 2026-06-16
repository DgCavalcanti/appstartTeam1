# Documento de Requisitos — Sistema de Apoio à Alocação Ambulatorial (SAA)

## 1. Introdução

### 1.1 Objetivo do Documento

Este documento descreve os requisitos funcionais e não funcionais do Sistema de Apoio à Alocação Ambulatorial (SAA), conforme implementado. Ele serve como referência técnica para a documentação exigida no checklist do Demo Day, item "Documentação dos requisitos (técnico)".

### 1.2 Definições, Siglas e Abreviações

| Termo | Definição |
|---|---|
| SAA | Sistema de Apoio à Alocação Ambulatorial — módulo responsável por organizar a ocupação de salas ambulatoriais. |
| AGHU | Sistema de Gestão Hospitalar de origem dos dados reais de grades e consultas (fonte externa, integrada via importação de CSV). |
| Grade | Registro de atendimento ambulatorial programado (especialidade, profissional, dia da semana e turno). |
| Alocação | Vínculo entre uma grade e uma sala física, em um dia e turno específicos. |
| Conflito | Inconsistência detectada pelo motor de regras entre grades, salas, restrições e alocações. |
| RF / RNF | Requisito Funcional / Requisito Não Funcional. |
| MVP | Minimum Viable Product — versão mínima viável do sistema, atualmente em produção. |
| AD / LDAP | Active Directory — serviço de diretório institucional utilizado para autenticação dos usuários. |
| JWT | JSON Web Token — padrão de token utilizado para autenticação das requisições à API. |
| CSV | Comma-Separated Values — formato de arquivo utilizado para importação e exportação de dados. |

### 1.3 Visão Geral do Sistema

O SAA é composto por uma API backend (FastAPI/Python) e uma aplicação web frontend (Vue 3). O sistema apoia a decisão de alocação de salas ambulatoriais a partir de dados de grade de atendimento, cadastro de salas, restrições técnicas e alocações vigentes, identificando automaticamente conflitos entre eles e permitindo o ajuste manual das alocações com registro de histórico e justificativa.

## 2. Descrição Geral

### 2.1 Contexto e Escopo

Este documento cobre exclusivamente o módulo SAA e sua integração com dados reais do AGHU (grades e consultas importadas via CSV). Módulos legados do mesmo backend — pacientes, AIH, BPA, materiais e administração geral — não fazem parte do escopo do SAA e não são tratados neste documento.

### 2.2 Perfis de Usuário

| Perfil | Descrição |
|---|---|
| Usuário autenticado | Acessa o painel, consulta grades/salas/restrições/alocações, importa CSVs, realiza ajustes manuais de alocação e consulta o histórico. |
| Administrador | Usuário autenticado com privilégio adicional (isAdmin), com acesso à área de Administração do sistema. |
| Visitante (não autenticado) | Acesso restrito; é redirecionado à tela de login para áreas protegidas. |

### 2.3 Arquitetura e Persistência de Dados

- Backend: API REST construída em FastAPI (Python), organizada em camadas de rotas, controladores e provedores/serviços.
- Frontend: aplicação single-page em Vue 3 (Composition API) com Vue Router.
- Persistência principal das entidades do SAA (salas, restrições, alocações, grades e consultas AGHU): arquivos CSV em disco (`data/salas.csv`, `data/restricoes.csv`, `data/alocacoes.csv`, `data/vw_grades.csv`, `data/vw_consultas_2026.csv`).
- Histórico de ajustes de alocação: banco de dados SQLite (`data/saa.db`).
- Conexão opcional com PostgreSQL para dados do AGHU, inicializada na subida da aplicação quando configurada (`POSTGRES_DSN`).
- Autenticação: integração com Active Directory institucional (domínio EBSERHNET), com emissão de token JWT e, opcionalmente, cookie de refresh token (HttpOnly) para a opção "Lembrar de mim".

## 3. Requisitos Funcionais

| ID | Descrição |
|---|---|
| RF01 | Autenticar usuários por meio de credenciais do Active Directory institucional, emitindo um token de acesso JWT. |
| RF02 | Oferecer a opção "Lembrar de mim", emitindo um cookie de refresh token (HttpOnly) para renovação automática do acesso. |
| RF03 | Permitir o encerramento de sessão (logout), invalidando o refresh token e removendo o cookie correspondente. |
| RF04 | Importar arquivos CSV de Grades AGHU e Consultas AGHU, validando o formato do cabeçalho e fazendo backup automático do arquivo anterior antes da substituição. |
| RF05 | Importar arquivos CSV de Salas, Restrições e Alocações. |
| RF06 | Listar e filtrar Grades AGHU por especialidade, turno, dia da semana e situação da grade. |
| RF07 | Apresentar um resumo agregado das Grades AGHU (capacidade, contagens por especialidade/dia/turno). |
| RF08 | Listar e filtrar Salas por bloco, status e especialidade preferencial; exibir detalhes de uma sala específica. |
| RF09 | Listar Restrições técnicas associadas às salas (equipamento obrigatório ou especialidade exclusiva). |
| RF10 | Listar e filtrar Alocações vigentes (vínculo grade × sala × dia × turno). |
| RF11 | Calcular automaticamente os conflitos entre grades, salas, restrições e alocações, classificando-os por gravidade (crítico, operacional, informativo). |
| RF12 | Permitir o ajuste manual de uma alocação (troca de sala), simulando os conflitos antes e depois da mudança. |
| RF13 | Exigir justificativa textual quando o ajuste manual resultar em conflito crítico ou operacional; bloquear a confirmação sem essa justificativa. |
| RF14 | Registrar o histórico de cada ajuste de alocação (usuário responsável, data/hora, sala anterior, sala nova, justificativa e conflitos antes/depois) e permitir sua consulta. |
| RF15 | Apresentar um painel (dashboard) com indicadores gerais (total de salas, disponíveis, bloqueadas, em reforma/manutenção, conflitos críticos) e a lista de conflitos detectados, com filtros por dia, turno e especialidade. |
| RF16 | Apresentar um resumo de capacidade ambulatorial agregada a partir dos dados reais do AGHU. |
| RF17 | Listar e filtrar Consultas AGHU por especialidade, unidade funcional, profissional, turno, dia da semana, situação e consultas excedentes; apresentar resumos por especialidade e por dia/turno. |
| RF18 | Apresentar um relatório de qualidade dos dados importados, identificando problemas encontrados. |
| RF19 | Restringir o acesso à área de Administração a usuários com privilégio de administrador, exibindo "Acesso Negado" aos demais. |

## 4. Requisitos Não Funcionais

| ID | Categoria | Descrição |
|---|---|---|
| RNF01 | Segurança | Autenticação via AD/LDAP institucional; tokens JWT com expiração configurável (mais curta quando "Lembrar de mim" está marcado); refresh token armazenado em cookie HttpOnly. |
| RNF02 | Auditoria | Todo ajuste manual de alocação registra o usuário responsável (cabeçalho `X-Usuario` da requisição) e a justificativa, quando exigida. |
| RNF03 | Desempenho | Endpoints de consulta sobre dados do AGHU retornam resultados paginados/agregados no servidor (limite de 5.000 linhas para grades e 1.000 para consultas), evitando o retorno de grandes volumes brutos ao cliente. |
| RNF04 | Confiabilidade de dados | Toda importação de CSV gera backup automático do arquivo substituído (pasta `data/importados`, com timestamp) antes da sobrescrita. |
| RNF05 | Usabilidade | Interface integralmente em português, com indicadores visuais por cor (status de sala, gravidade de conflito) no painel. |
| RNF06 | Persistência | Dados do SAA mantidos em arquivos CSV; histórico de ajustes em banco SQLite; integração opcional com PostgreSQL para dados do AGHU. |
| RNF07 | Compatibilidade | API REST documentada (FastAPI) consumida por uma aplicação web SPA (Vue 3), permitindo evolução independente de backend e frontend. |

## 5. Regras de Negócio — Motor de Detecção de Conflitos

O motor de conflitos avalia, a cada consulta ao painel ou simulação de ajuste, o conjunto de grades, salas, restrições e alocações vigentes, aplicando as seguintes regras:

| Código | Descrição | Gravidade |
|---|---|---|
| C01 | Sala em reforma sendo utilizada em uma alocação. | crítico |
| C02 | Sala em manutenção sendo utilizada em uma alocação. | crítico |
| C03 | Sala bloqueada sendo utilizada em uma alocação. | crítico |
| C04 | Alocação referenciando uma sala inexistente. | crítico |
| C05 | Alocação referenciando uma grade inexistente. | crítico |
| C06 | Dupla alocação — duas grades atribuídas à mesma sala, no mesmo dia e turno. | crítico |
| C07 | Grade sem nenhuma sala associada. | crítico |
| C08 | Especialidade da grade incompatível com a especialidade preferencial da sala. | operacional |
| C09 | Equipamento obrigatório (definido em uma restrição) ausente na sala. | operacional |
| C10 | Atendimento de ortopedia alocado em sala inacessível ou em andar alto (alerta, não bloqueante). | operacional |

Regra adicional de fluxo: ao simular um ajuste manual de alocação, se a nova configuração gerar qualquer conflito de gravidade crítica ou operacional, o sistema exige uma justificativa textual do usuário antes de permitir a confirmação do ajuste.

## 6. Restrições e Limitações do MVP

- Não há alocação automática: o sistema oferece apenas o ajuste manual de alocações, assistido por simulação de conflitos. O endpoint de alocação automática não existe nesta versão.
- Um motor de alocação automática (`alocacao_engine.py`) está presente no código-fonte como módulo experimental/futuro, mas não é utilizado pela API atual.
- A persistência principal das entidades do SAA é feita em arquivos CSV, e não em um banco de dados transacional completo.
- A importação de dados substitui o arquivo vigente (com backup automático do anterior); não há versionamento incremental linha a linha.

## 7. Considerações Finais

Os requisitos aqui descritos refletem o estado atual da implementação do SAA e fundamentam a avaliação técnica prevista no checklist do Demo Day, em conjunto com os documentos de Casos de Uso e Manual Básico de Utilização.
