# Integração com CSVs Reais do AGHU

## Problema Resolvido

O projeto SAA utilizava um CSV simplificado de grades com formato próprio.
Os dados reais exportados pelo AGHU possuem campos diferentes, semântica diferente
e volume muito maior (centenas de milhares de linhas em consultas).

Esta integração adapta o projeto para consumir os CSVs reais sem quebrar
a arquitetura existente e sem expor dados brutos ao frontend.

---

## Origem dos Dados

| Arquivo | Origem | Frequência |
|---------|--------|------------|
| `vw_grades.csv` | View AGHU — grades ambulatoriais | Sob demanda |
| `vw_consultas_2026.csv` | View AGHU — consultas ambulatoriais | Sob demanda |

---

## Colunas Utilizadas

### vw_grades.csv

| Coluna AGHU | Campo Interno | Tipo | Observação |
|-------------|---------------|------|------------|
| `Grade` | `grade_id` | `str` | Preservado como string (zeros à esquerda mantidos) |
| `Profissional_Grade` | `profissional` | `str` | |
| `Unidade_Funcional` | `unidade_funcional` | `str` | |
| `Condicao_De_Atendimento` | `condicao_atendimento` | `str` | |
| `Especialidade` | `especialidade` | `str` | |
| `Situacao_Atual_Grade` | `situacao_grade` | `str` | |
| `Dia_da_Semana` | `dia_semana` | `str` | |
| `Hora_Inicio` | `hora_inicio` | `str \| None` | Opcional |
| `Turno` | `turno` | `str` | |
| `Situacao_Atual_Horario` | `situacao_horario` | `str` | |
| `Quantidade_Vagas` | `quantidade_vagas` | `int` | **Veja regra crítica abaixo** |
| *(calculado)* | `qtd_salas_necessarias` | `int` | Sempre **1** no MVP |

### vw_consultas_2026.csv

| Coluna AGHU (possíveis nomes) | Campo Interno | Tipo |
|-------------------------------|---------------|------|
| `Num_Consulta` / `Num_Consulta_Aghu` | `consulta_id` | `str \| None` |
| `Grade` | `grade_id` | `str \| None` |
| `Profissional` / `Profissional_Grade` | `profissional` | `str \| None` |
| `Unidade_Funcional` | `unidade_funcional` | `str \| None` |
| `Especialidade` | `especialidade` | `str \| None` |
| `Sigla_Especialidade` | `sigla_especialidade` | `str \| None` |
| `Data_Hora_Consulta` / `Dt_Hr_Consulta` | `data_hora_consulta` | `str \| None` (ISO 8601) |
| `Dia_da_Semana` | `dia_semana` | `str \| None` |
| `Turno` | `turno` | `str \| None` |
| `Situacao_Consulta` / `Situacao_Da_Consulta` | `situacao_consulta` | `str \| None` |
| `Condicao_De_Atendimento` / `Condicao_Do_Atendimento` | `condicao_atendimento` | `str \| None` |
| `Retorno` | `retorno` | `bool \| None` |
| `Consulta_Excedente` | `consulta_excedente` | `bool \| None` |
| `Paciente_Presente` | `paciente_presente` | `bool \| None` |

> Algumas extrações reais do AGHU usam `Situacao_Da_Consulta` e
> `Condicao_Do_Atendimento` em vez de `Situacao_Consulta` /
> `Condicao_De_Atendimento`. Ambas as variantes são aceitas — o provider
> normaliza para o nome canônico na leitura (ver "Transformações Aplicadas").

---

## Regra Crítica: Quantidade_Vagas ≠ Número de Salas

> **`Quantidade_Vagas` representa a capacidade de atendimento/vagas planejadas,
> NÃO o número de salas físicas.**

No AGHU, cada linha da grade define quantas consultas estão programadas para
aquele profissional/especialidade/dia/turno. Esse número **não** corresponde
ao número de salas necessárias para atender a demanda.

### No MVP:
- `quantidade_vagas` → campo próprio, preservado como `int`.
- `qtd_salas_necessarias` → **sempre `1`** por grade/horário/profissional.

Isso respeita a semântica real do dado e evita alocação incorreta de salas.

### Regra futura (pós-MVP):
A necessidade de salas poderá ser calculada com base em:
- Tempo médio de atendimento por especialidade
- Capacidade de atendimento por sala
- Configurações específicas da unidade funcional

---

## Transformações Aplicadas

### Grades
1. Detecção automática de encoding (`utf-8-sig` → `utf-8` → `latin-1`).
2. Reparo automático de *mojibake* (ver seção abaixo).
3. Detecção automática de separador (`,` ou `;`).
4. Normalização de nomes de colunas (trim, remoção de BOM).
5. `Grade` preservado como string (zeros à esquerda não são perdidos).
6. `Quantidade_Vagas` convertida para `int` (falha retorna `0`).
7. `Hora_Inicio` é opcional — `None` quando ausente.
8. `qtd_salas_necessarias = 1` fixo.
9. Linhas com `Grade` vazio são ignoradas com aviso.
10. Colunas extras no CSV são ignoradas silenciosamente.

### Consultas
1. Mesmo processo de encoding, reparo de mojibake e separador.
2. Datas convertidas para ISO 8601 quando possível.
3. Flags booleanas (`S`/`N`, `SIM`/`NÃO`, `TRUE`/`FALSE`, `1`/`0`) → `bool`.
4. Múltiplos nomes de coluna aceitos (`Num_Consulta` ou `Num_Consulta_Aghu`,
   `Situacao_Consulta` ou `Situacao_Da_Consulta`, `Condicao_De_Atendimento`
   ou `Condicao_Do_Atendimento`, etc.).
5. Cache interno evita releitura do CSV em múltiplas chamadas por request.

### Reparo de mojibake (encoding duplo)

Algumas exportações do AGHU (ex.: planilhas reabertas/resalvas) chegam com
caracteres acentuados corrompidos — texto UTF-8 válido que foi decodificado
como CP1252/Latin-1 e regravado em UTF-8, produzindo sequências como
`ManhÃ£` (em vez de `Manhã`) ou `AMBULATÃ“RIO` (em vez de `AMBULATÓRIO`).

Os providers de grades e consultas detectam e corrigem isso automaticamente
fazendo um round-trip (`texto.encode("cp1252").decode("utf-8")`) logo após a
leitura do arquivo. Texto já corretamente codificado em UTF-8 quase sempre
falha nesse round-trip (gera bytes inválidos), então a correção só é
aplicada quando o round-trip realmente funciona — arquivos sem esse
problema não são afetados.

---

## Regras de Negócio

| Situação | Classificação |
|----------|---------------|
| AGENDADO, MARCADO, CONFIRMADO, PRESENTE, REALIZADO | `marcada` |
| LIVRE, DISPONIVEL | `livre` |
| BLOQUEADO, BLOQUEIO | `bloqueio` |
| `Consulta_Excedente = S` | excedente (flag independente) |

**Taxa de Ocupação** = marcadas / (marcadas + livres)

**Taxa de Excedente** = excedentes / total de consultas

---

## Limitações

1. O CSV inteiro é lido na memória do backend. Para arquivos muito grandes (>500 MB),
   considerar streaming ou banco de dados intermediário.
2. A classificação de situações assume os valores descritos acima. Situações
   novas no AGHU serão classificadas como "outra" sem erro.
3. A relação entre grades e consultas é feita pelo campo `Grade` (string).
   Se o AGHU exportar formatos diferentes, o cruzamento pode não funcionar.
4. `qtd_salas_necessarias = 1` é uma aproximação do MVP — não reflete a
   realidade de especialidades que precisam de múltiplas salas simultaneamente.

---

## Próximos Passos

- [ ] Persistir os dados importados em banco de dados (evitar re-leitura do CSV a cada request).
- [ ] Calcular `qtd_salas_necessarias` com base em regras por especialidade.
- [ ] Cruzamento automático entre grades ativas e consultas para detectar gaps.
- [ ] Exportação de relatórios (PDF/Excel) a partir dos indicadores calculados.
- [ ] Histórico de importações com diff entre versões do CSV.
- [ ] Suporte a upload incremental (apenas delta desde a última importação).
