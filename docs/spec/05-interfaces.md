# Interfaces e Integrações

## 1. Hardware
* Computador da gestão ambulatorial (uso local, sem servidor dedicado).

## 2. Software
* Entrada: grade exportada do AGHU em .csv ou .xlsx.
* Persistência: SQLite local; sem integração direta com o AGHU.

## 3. API REST
Endpoints organizados por recurso. As telas de planilha usam edição em lote (enviam as células alteradas). Não há autenticação — uso local.

| Grupo | Método | Rota | Para quê |
|---|---|---|---|
| Importação | POST | `/api/importacao` | Prévia: trata a grade e simula a alocação (nada é gravado) |
| Cenários | GET / POST | `/api/cenarios` | Listar o histórico e criar um cenário a partir da importação |
| | GET | `/api/cenarios/padroes` | Mapa do HC (pavimentos) e malha de turnos do catálogo |
| | GET / DELETE | `/api/cenarios/{id}` | Abrir ou excluir um cenário |
| | POST | `/api/cenarios/{id}/clonar` | Duplicar um cenário para criar uma variação |
| Etapas | GET | `/api/cenarios/{id}/etapas` | Status das 6 etapas |
| | POST | `/api/cenarios/{id}/etapas/{numero}` | Ir para uma etapa |
| | POST | `/api/cenarios/{id}/concluir` | Concluir o cenário |
| Grades (etapa 2) | GET / PUT | `/api/cenarios/{id}/grades` | Ler/editar as contagens de grades e a participação |
| Panorama (etapa 3) | GET / PUT | `/api/cenarios/{id}/panorama` | Ler/editar as salas por pavimento |
| Restrições (etapa 4) | GET / POST / DELETE | `/api/cenarios/{id}/restricoes` | Ler, definir e remover obrigatoriedades/preferências |
| Execução (etapa 5) | POST | `/api/cenarios/{id}/alocar` | Executar o motor de alocação |
| Ajustes (etapa 6) | PUT | `/api/cenarios/{id}/resultado` | Ajustar o resultado manualmente |
| Visualização | GET | `/api/cenarios/{id}/visualizacao` | Painel consolidado, somente leitura |

A documentação interativa (Swagger/OpenAPI) é gerada automaticamente pelo FastAPI em `/docs`.

## 4. Módulos da interface

### 4.1 Importação e Alocação
Porta de entrada (etapa 1). Recebe o arquivo do AGHU, exibe o relatório de redução em funil, a lista de unidades com a participação padrão do catálogo, o panorama de salas editável e a simulação da alocação. Permite salvar como cenário e gerencia o histórico (abrir, clonar, excluir).

### 4.2 Cenário (as 6 etapas)
Uma tela por cenário, com um **stepper** que mostra o selo de status de cada etapa e permite voltar a qualquer uma. Cada etapa exibe seu painel: grades (2), panorama (3), restrições (4), execução (5) e ajustes (6).

### 4.3 Componente de planilha editável
Reusado nas etapas 2, 3 e 6. Edição por célula, navegação por teclado, colar do Excel e rodapé de totais. Menos código, comportamento consistente.

### 4.4 Visualização (painel consolidado)
Somente leitura. Indicadores gerais (grades alocadas, sem sala, salas no pico, ocupação média), gráfico de ocupação por turno, medidores de ocupação por pavimento (em salas físicas) e a distribuição das clínicas. A distribuição separa **Pavimento** e **Bloco** em colunas e permite filtrar por bloco, por pavimento (cruzando blocos) e buscar por clínica.

### 4.5 Componentes de indicadores
Medidores e tabelas de ocupação reusados na execução (etapa 5) e na visualização, com a conversão de estações de volta para salas físicas.
