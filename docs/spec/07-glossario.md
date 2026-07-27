# Glossário e Referências

## 1. Termos Técnicos
* **SAA**: Sistema de Alocação Ambulatorial.
* **AGHU**: Aplicação de Gestão para Hospitais Universitários (origem da grade).
* **Unidade funcional / Clínica**: a especialidade ou serviço ambulatorial que ocupa consultórios (ex.: Cardiologia, Ortopedia).
* **Pavimento**: um andar de um bloco do prédio (ex.: "Bloco E — 2º Pavimento"), onde uma clínica é alocada para a semana inteira.
* **Bloco**: agrupamento de pavimentos do prédio (ex.: Bloco D, E, F, Anexo).
* **Estação**: unidade de capacidade. Uma sala de 2 estações comporta dois atendimentos ao mesmo tempo e vale 2.
* **Turno**: um dos 10 períodos do modelo — 5 dias (segunda a sexta) × 2 (manhã, tarde). O turno "Noite" fica fora desta versão.
* **Cenário**: uma alocação completa e autocontida; a raiz do histórico.
* **grade_slot**: camada de origem da demanda — uma linha por profissional × dia × turno tratado.
* **grade_demanda**: camada derivada — a contagem de grades por unidade/dia/turno, que a etapa 2 edita.
* **Obrigatoriedade**: restrição rígida que trava uma clínica num pavimento; única capaz de gerar grade não alocada.
* **Preferência / Afinidade**: restrição flexível que atrai uma clínica a um pavimento, mas cede se ele não a comporta.
* **Estação vs. sala**: o motor conta capacidade em estações; os relatórios convertem de volta para salas físicas.
* **Cenário desatualizado**: quando um insumo (grades, salas ou restrições) muda depois da alocação, esta é marcada como desatualizada — o sistema avisa em vez de apagar.

## 2. Ferramentas
* **FastAPI**: framework Python para APIs.
* **SQLAlchemy / Alembic**: ORM e versionamento de esquema.
* **pandas**: tratamento tabular na importação.
* **Vue / Pinia / Vite / Tailwind**: interface reativa.

## 3. Referências
* Documento de arquitetura do SAA (v3, motor de alocação co-desenhado e validado).
* Planilhas de referência do HC: "Quantitativo de Consultórios" e "Grades AGHU — Validação".
