# Documento de Visão

## 1. Problema e Oportunidade
* **O Problema**: A distribuição das grades de atendimento das clínicas nos consultórios do HC-UFPE é feita manualmente, dependendo de conhecimento tácito e planilhas dispersas. Definir em qual pavimento cada clínica atende durante a semana, respeitando a capacidade de cada andar, é trabalhoso e sujeito a erro.
* **Impacto**: Ocupação desequilibrada dos pavimentos, dificuldade de comparar alternativas de distribuição e retrabalho a cada nova grade exportada do AGHU.
* **Solução Proposta**: O SAA (Sistema de Alocação Ambulatorial) importa a grade do AGHU, trata os dados e executa um motor que aloca cada clínica inteira em um pavimento, para a semana toda, respeitando a capacidade em estações. O gestor revisa e ajusta o resultado por um fluxo de seis etapas, e cada alocação fica guardada como um cenário independente, formando um histórico comparável.

## 2. Partes Interessadas (Stakeholders)
* Gestor Ambulatorial / Chefia do Ambulatório — único operador do sistema.
* Profissional assistencial (beneficiário indireto da organização das clínicas).
* Administrador Técnico (instala e mantém a aplicação local).

## 3. Escopo do Produto
* Importação da grade exportada do AGHU (.csv/.xlsx) com tratamento e redução dos dados na entrada.
* Alocação automática de cada clínica (unidade funcional) em um pavimento, para a semana inteira, com capacidade contada em estações.
* Edição, como planilha, das grades por turno, do panorama de salas e do resultado da alocação.
* Definição de obrigatoriedades (rígidas) e preferências (flexíveis) por clínica.
* Histórico de cenários autocontidos, com clonagem para comparar variações.
* Painel de visualização consolidado, somente leitura, com filtros por bloco e pavimento.
* *Limites*: uso local por um único gestor, sem login e sem concorrência; sem escrita de volta no AGHU; turno "Noite" fora do modelo (10 turnos).

## 4. Metas e Objetivos de Negócio
* Produzir uma distribuição de clínicas por pavimento sem grades sem sala, quando houver capacidade.
* Tornar reprodutível e auditável a decisão de alocação, preservando os insumos de cada cenário.
* Reduzir o tempo e a dependência de conhecimento informal para reorganizar o ambulatório a cada nova grade.
* Permitir que o gestor compare alternativas (cenários) antes de decidir.
