# SPEC.md - Contrato de Desenvolvimento (SDD)

## 1. Visão Geral e Resultados Esperados
Este documento orienta a evolução do SAA — Sistema de Alocação Ambulatorial. O objetivo é alocar cada clínica (unidade funcional) em um pavimento do HC, para a semana inteira, a partir da grade exportada do AGHU, com uso local por um único gestor.

### Objetivos de Alto Nível
* [x] Importar e tratar a grade do AGHU, reduzindo-a a contagens por unidade/dia/turno.
* [x] Alocar automaticamente cada clínica em um pavimento, respeitando a capacidade em estações.
* [x] Permitir editar grades, panorama de salas e resultado como planilha, e definir obrigatoriedades/preferências.
* [x] Guardar cada alocação como um cenário autocontido, com histórico e clonagem.
* [x] Exibir um painel consolidado de visualização, somente leitura.

## 2. Contexto do Projeto
As definições detalhadas estão distribuídas nos seguintes documentos:
- [Visão](01-visao.md)
- [Requisitos](02-requisitos.md)
- [Casos de Uso](03-casos-uso.md)
- [Modelo de Dados](04-modelo-dados.md)
- [Interfaces](05-interfaces.md)
- [Arquitetura](06-arquitetura.md)
- [Glossário](07-glossario.md)

A referência de projeto é o documento de arquitetura do SAA (v3), com o motor de alocação co-desenhado e validado sobre os dados reais do HC.

## 3. Limites de Escopo e Guardrails

**A implementação DEVE:**
- Seguir o Modelo de Dados de `04-modelo-dados.md` (cenário autocontido).
- Manter as regras de negócio no domínio, em Python puro e testável isoladamente.
- Respeitar o fluxo em camadas: API → Serviço → Domínio → Repositório.
- Derivar a capacidade dos pavimentos das contagens de salas, em estações.
- Implementar testes para cada regra de domínio, serviço ou componente novo.

**A implementação NÃO DEVE:**
- Persistir as linhas brutas do AGHU (só grade_slot e grade_demanda).
- Deixar a preferência forçar sobra — só a obrigatoriedade força.
- Colocar regra de negócio no router nem lógica de alocação no frontend.
- Acessar ou escrever diretamente na base do AGHU.
- Introduzir autenticação, RBAC ou multiusuário sem mudança explícita de escopo.

## 4. Estado da Implementação

### Domínio (Python puro)
- [x] Malha de 10 turnos e capacidade em estações.
- [x] Pipeline de importação (10 passos), validado no arquivo real do AGHU.
- [x] Motor de alocação heurístico atrás da interface `SolverAlocacao`.
- [x] Máquina de estados das 6 etapas com regra de invalidação.

### Persistência e API
- [x] Modelo de dados (10 tabelas) em SQLAlchemy + migração Alembic.
- [x] Repositórios (cenário e catálogo) e catálogo semeado com o mapa real do HC.
- [x] Camada de serviços (importação, grades, panorama, restrições, alocação, visualização).
- [x] API REST por recurso, com edição em lote.

### Frontend
- [x] Tela de importação e alocação, com histórico e clonagem.
- [x] Tela do cenário com stepper e as 6 etapas.
- [x] Componente de planilha editável reusado nas etapas 2, 3 e 6.
- [x] Painel de visualização com filtros por bloco e pavimento.

### Pendências
- [ ] Decisões de produto em aberto: distribuição concentrada vs. espalhada sem preferência; pesos do histórico na afinidade; exportação (Excel/PDF) da visualização.
- [ ] Evolução futura: solver exato (OR-Tools) plugável na interface `SolverAlocacao`.

## 5. Critérios de Verificação Global
- [x] O pipeline reproduz a redução do arquivo real (≈5.695 → ≈1.400 slots → 347 demandas).
- [x] Baseline sem restrições: 43 clínicas alocadas em 9 pavimentos úteis, zero grades sem sala.
- [x] Obrigatoriedade gera sobra repartida proporcionalmente; preferência nunca gera sobra havendo espaço.
- [x] Alterar um insumo (etapas 1–4) marca a alocação como desatualizada sem apagar o resultado.
- [x] A capacidade é sempre derivada das contagens; os relatórios convertem estações em salas físicas.
- [x] Cada cenário é reabrível com os insumos que o geraram; clonar não afeta a origem.
