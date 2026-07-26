# Interfaces e Integrações

## 1. Protótipos
* [Protótipo em HTML](assets/painel_ocupacao_prototipo.html)

## 2. Hardware
* Computadores da gestão ambulatorial.
* Computadores administrativos.

## 3. Software
* No MVP, leitura de dados por CSV.
* Evolução para integração com AGHU por meio de Provider/API.

## 4. API Endpoints

| Módulo | Endpoint | Descrição |
|---|---|---|
| Grades | `GET /api/grades` | Lista todas as grades |
| | `GET /api/grades/{id_grade}` | Detalha uma grade específica |
| | `GET /api/grades?dia_semana=&turno=` | Filtra por dia e turno |
| Salas | `GET /api/salas` | Lista todas as salas |
| | `GET /api/salas/{id_sala}` | Detalha uma sala específica |
| | `GET /api/salas?status=disponivel` | Filtra por status |
| Restrições | `GET /api/restricoes` | Lista todas as restrições |
| | `GET /api/restricoes/{especialidade}` | Restrições por especialidade |
| Alocações | `GET /api/alocacoes` | Lista todas as alocações |
| | `GET /api/alocacoes?dia_semana=&turno=` | Filtra por dia e turno |
| | `POST /api/alocacoes/ajustar` | Ajuste manual assistido |
| Conflitos | `GET /api/dashboard/conflitos?...` | Lista conflitos com filtros |

## 5. Módulos da interface

### 5.1 Módulo de Grades

Exibe a demanda de atendimento por especialidade, dia e turno. Permite filtragem por dia, turno e especialidade, e visualização da quantidade de salas necessárias por grade.

### 5.2 Módulo de Salas

Exibe as salas disponíveis e suas características — bloco, andar, status, equipamentos, acessibilidade e especialidade preferencial.

### 5.3 Módulo de Restrições

Registra e exibe regras básicas por especialidade, dando suporte à validação de conflitos no backend.

### 5.4 Módulo de Alocações

Mostra a associação entre grades e salas. Permite filtrar por dia e turno e realizar ajuste manual assistido via endpoint POST.

### 5.5 Módulo de Conflitos

Identifica inconsistências entre grades, salas, restrições e alocações. Tipos de conflito no MVP:

* Sala bloqueada (reforma/manutenção) em uso
* Oftalmologia em sala sem equipamento
* Ortopedia em sala sem acessibilidade adequada
* Sala usada por mais de uma grade no mesmo turno
* Especialidade distribuída em blocos distantes

### 5.6 Dashboard SAA

Centraliza a visualização operacional com filtros por dia/turno/especialidade, cards de resumo, grid de salas com código de cores e tabela de ocupação.
Cores do grid de salas:

* Verde: disponível
* Azul: alocada corretamente
* Amarelo: alerta
* Cinza: bloqueada
* Vermelho: conflito crítico