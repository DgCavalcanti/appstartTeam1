# SPEC.md - Contrato de Desenvolvimento (SDD)

## 1. Visão Geral e Resultados Esperados
Este documento é a ÚNICA fonte de verdade para a orquestração do desenvolvimento. O objetivo é construir um sistema hospitalar seguro e em conformidade com a LGPD.

### Objetivos de Alto Nível
* [ ] Ler dados de grades, salas, restrições e alocações a partir de arquivos CSV.
* [ ] Cruzar grades e salas para exibir a distribuição planejada e a ocupação por turno.
* [ ] Identificar automaticamente conflitos básicos de alocação.
* [ ] Permitir ajuste manual assistido via dashboard operacional.

## 2. Contexto do Projeto (Documentação Imutável)
As definições detalhadas estão distribuídas nos seguintes documentos:
- [Visão](01-visao.md)
- [Requisitos](02-requisitos.md)
- [Casos de Uso](03-casos-uso.md)
- [Modelo de Dados](04-modelo-dados.md)
- [Interfaces](05-interfaces.md)
- [Arquitetura](06-arquitetura.md)
- [Glossário](07-glossario.md)

## 3. Limites de Escopo e Guardrails (Anti-Patterns)
**A IA DEVE:**
- Seguir rigorosamente o Modelo de Dados definido em `04-modelo-dados.md`.
- Implementar testes unitários para cada funcionalidade nova.
- Utilizar criptografia AES-256 para dados sensíveis.
- Respeitar o fluxo em camadas unidirecional: Frontend Vue -> Router FastAPI -> Controller -> Provider CSV -> Arquivo CSV
- Manter a separação estrita entre interface, API, regra de negócio e acesso aos dados.

**A IA NÃO DEVE:**
- Criar dependências externas não documentadas em `06-arquitetura.md`.
- Implementar exclusão física de registros (usar Soft Delete).
- Burlar o sistema de RBAC (Role-Based Access Control).
- Desenvolver alocação automática.
- Tentar acessar ou modificar diretamente a base de dados do AGHU na fase do MVP.
- Usar sincronização em tempo real.

## 4. Task Breakdown (Plano de Implementação)
### Fase 1: Dados e Backend (MVP com CSV)
- [ ] [TASK-001] Implementar leitura inicial de dados por CSV seguindo o padrão do framework.
- [ ] [TASK-002] Implementar o arquivo `grade_csv_provider.py`.
- [ ] [TASK-003] Criar `grade_controller.py` e `grade.py` (router).
- [ ] [TASK-004] Registrar o router de grades no arquivo `main.py`.
- [ ] [TASK-005] Repetir o padrão de arquitetura para os módulos de salas, restrições e alocações.
- [ ] [TASK-006] Criar a lógica de conflitos no controller.
- [ ] [TASK-007] Implementar alertas básicos de conflito na lógica de negócio.

### Fase 2: Frontend e Visualização
- [ ] [TASK-008] Criar stores Pinia e telas Vue.
- [ ] [TASK-009] Criar módulo de visualização das grades.
- [ ] [TASK-010] Criar módulo de cadastro e visualização das salas.
- [ ] [TASK-011] Criar tela de cruzamento entre grades e salas para exibir a distribuição atual.
- [ ] [TASK-012] Criar e testar o dashboard SAA.

### Fase 3: Funcionalidades Operacionais 
- [ ] [TASK-013] Criar o fluxo de ajuste manual assistido para alocação.
- [ ] [TASK-014] Registrar histórico dos ajustes realizados durante o fluxo manual.

### Fase 4: Validação, Documentação e Próximos Passos (AGHU)
- [ ] [TASK-015] Testar o fluxo completo end-to-end da aplicação.
- [ ] [TASK-016] Documentar todos os endpoints da API utilizando OpenAPI / Swagger.
- [ ] [TASK-017] Definir quais dados do AGHU serão necessários para substituir futuramente os arquivos CSV.
- [ ] [TASK-018] Preparar apresentação do MVP do Sistema de Apoio à Alocação Ambulatorial.

## 5. Critérios de Verificação Global
- [ ] 100% de cobertura em rotas de autenticação.
- [ ] Zero vulnerabilidades críticas no lint de segurança.
- [ ] Conformidade total com os esquemas JSON/OpenAPI.
- [ ] Todos os endpoints implementados e protegidos por JWT
- [ ] Dashboard exibe cards de resumo e o grid de salas é exibido com códigos de cor.
- [ ] O sistema identifica conflitos básicos de alocação de forma automática.
- [ ] Rotas sensíveis utilizam e validam corretamente os tokens JWT