# Manual Básico de Utilização — Sistema de Apoio à Alocação Ambulatorial (SAA)

## 1. Introdução

Este manual apresenta, de forma prática e passo a passo, como utilizar o Sistema de Apoio à Alocação Ambulatorial (SAA). É destinado aos usuários que irão operar o sistema no dia a dia: importar dados, consultar o painel de indicadores, ajustar alocações de salas e acompanhar o histórico de mudanças.

## 2. Acessando o Sistema

Na tela inicial de Login:

1. Informe o usuário no campo "Usuário", no formato `EBSERHNET\seu.usuario`.
2. Informe a senha no campo "Senha". É possível alternar a exibição da senha pelo ícone de olho.
3. Marque "Lembrar de mim" caso deseje permanecer conectado por mais tempo neste dispositivo.
4. Clique em "Entrar". Em caso de erro, a mensagem será exibida abaixo do formulário.
5. Use o botão "Limpar" para apagar os campos preenchidos, se necessário.

## 3. Navegando pelo Menu Lateral

O menu lateral concentra todas as áreas do sistema, organizadas em grupos:

| Grupo | Itens do menu |
|---|---|
| Geral | Início |
| SAA — Alocação | Painel, Grades, Salas, Alocações, Importar CSV, Histórico |
| AGHU — Dados Reais | Capacidade, Consultas, Qualidade |
| Outros | Exemplos, Pacientes (se autenticado), Administração (apenas administradores) |

O ícone vermelho ao lado do item "Painel" indica, em tempo real, a quantidade de conflitos críticos pendentes.

## 4. Importando Dados (CSV)

Acesse "Importar CSV" no menu lateral. A tela apresenta um cartão para cada tipo de dado:

| Tipo | Arquivo | Colunas obrigatórias |
|---|---|---|
| Grades | grades.csv | Layout exportado do AGHU (validado automaticamente pelo sistema) |
| Consultas | consultas.csv | Layout exportado do AGHU (validado automaticamente pelo sistema) |
| Salas | salas.csv | id, numero, bloco, status (opcionais: andar, acessibilidade, equipamentos separados por ";", especialidade_preferencial) |
| Restrições | restricoes.csv | id, sala_id, tipo, valor |
| Alocações | alocacoes.csv | id, grade_id, sala_id, dia_semana, turno |

1. Clique em selecionar arquivo no cartão correspondente ao tipo de dado.
2. Escolha o arquivo CSV em seu computador.
3. Aguarde o processamento. Uma mensagem (toast) verde confirma o sucesso, indicando quantas linhas foram lidas e quantas foram consideradas válidas; uma mensagem vermelha indica erro.
4. O arquivo anteriormente carregado é automaticamente salvo como backup antes da substituição — nenhum dado anterior é perdido.
5. Após a importação, consulte o painel "Situação Atual dos Dados", na mesma tela, para confirmar as quantidades atualizadas de grades, consultas, salas, restrições e alocações.

A tela também exibe exemplos de formato de arquivo (`salas.csv` e `alocacoes.csv`) para referência rápida.

## 5. Consultando o Painel SAA

Acesse "Painel" no menu lateral para visualizar a situação geral da alocação de salas:

- Indicadores no topo: total de salas, salas disponíveis, bloqueadas, em reforma/manutenção, grades no filtro atual e conflitos críticos.
- Filtros disponíveis: dia da semana, turno, bloco e status da sala.
- Grade visual de salas: cada sala aparece como um cartão colorido — verde (disponível), vermelho (bloqueada), amarelo (em reforma/manutenção) ou azul (ocupada); o símbolo ⚠ indica que a sala possui algum conflito.
- Lista de conflitos identificados, com a gravidade de cada um (crítico ou operacional) e sua descrição.
- Tabela de ocupação: relação de cada grade com a sala alocada (ou "Sem sala", quando não houver alocação) e a quantidade de conflitos associados.
- Clique em uma sala da grade visual para ver seus detalhes completos em uma janela.

## 6. Consultando Grades, Salas, Restrições e Alocações

As telas "Grades", "Salas" e "Alocações" seguem o mesmo padrão: uma lista de registros com filtros no topo (especialidade, turno, dia, status, bloco, conforme a tela). A tela "Restrições" apresenta a lista completa de restrições técnicas cadastradas para as salas.

## 7. Ajustando uma Alocação

Para alterar a sala de uma alocação existente:

1. Acesse "Alocações" e localize a alocação desejada.
2. Selecione a nova sala de destino.
3. O sistema simula automaticamente os conflitos da situação atual e da situação proposta, exibindo-os para comparação.
4. Caso a nova configuração gere algum conflito crítico ou operacional, o sistema solicitará uma justificativa textual obrigatória antes de permitir a confirmação.
5. Preencha a justificativa (quando solicitada) e confirme o ajuste.
6. O sistema salva a nova alocação e registra automaticamente um item no histórico de ajustes.

## 8. Consultando o Histórico de Ajustes

Acesse "Histórico" no menu lateral para visualizar todos os ajustes de alocação já realizados, incluindo o usuário responsável, a data e hora, a sala anterior e a nova, a justificativa informada e os conflitos identificados antes e depois de cada ajuste.

## 9. Consultando Dados do AGHU

| Tela | O que mostra |
|---|---|
| Capacidade | Resumo agregado da capacidade ambulatorial calculado a partir dos dados reais importados do AGHU. |
| Consultas | Lista filtrável de consultas ambulatoriais (especialidade, unidade, profissional, turno, dia, situação, excedentes) e resumos por especialidade e por dia/turno. |
| Qualidade | Relatório com os problemas de qualidade identificados nos dados importados (ex.: inconsistências ou registros incompletos). |

## 10. Área de Administração

Disponível apenas para usuários com privilégio de administrador. Exibe as informações do usuário obtidas do Active Directory. Usuários sem esse privilégio que tentarem acessar verão a mensagem "Acesso Negado".

## 11. Encerrando a Sessão

Utilize a opção de logout no menu de perfil, no canto superior direito da tela, para encerrar a sessão de forma segura.

## 12. Dicas e Perguntas Frequentes

- **Importação rejeitada para Grades:** verifique se o arquivo exportado do AGHU mantém o layout de colunas original — o sistema valida esse formato automaticamente.
- **O que significa "conflito crítico"?** Indica uma inconsistência grave (ex.: sala bloqueada em uso, dupla alocação) que deve ser resolvida com prioridade.
- **O que significa "conflito operacional"?** Indica uma inconsistência de menor impacto (ex.: especialidade incompatível com a sala) que merece atenção, mas não bloqueia o funcionamento.
- **Não encontro um arquivo importado anteriormente:** ele foi preservado automaticamente como backup na pasta de importados antes da substituição.
- **Por que o sistema pede uma justificativa ao trocar a sala de uma alocação?** Isso ocorre apenas quando a simulação indica que a troca gera um conflito crítico ou operacional — é uma medida de controle e auditoria.
