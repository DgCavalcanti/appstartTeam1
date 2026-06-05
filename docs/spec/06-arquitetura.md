# Arquitetura e Segurança

## 1. Stack Técnica
* Frontend: 
    - Vue 3 + TypeScript + Vite 
    - Pinia (Gerenciamento de estado)
    - Axios (Requisições HTTP)
    - Vue Router + Tailwind CSS
* Backend: 
    - Python + FastAPI + Pydantic
    - JWT (Autenticação)
    - Providers em Python com leitura por CSV
* Banco de Dados: 
    - Arquivos CSV no MVP
    - sqlite, Banco de dados local para armazenar salas, restrições e histórico de uso

## 2. Auditoria
* Rastreamento completo: O sistema exige registrar quem realizou determinada alteração manual (data, hora e usuário).

## 3. Conformidade LGPD
* Dados reais de pacientes ou prontuário eletrônico ficam fora do escopo do MVP

## 4. Acessos
* O MVP utilizará a autenticação já implementada.
* Rotas sensíveis devem usar `Depends(auth_handler.decode_token)` baseadas em JWT
* Controle baseado em perfis de usuário: Gestor Ambulatorial (edição e importação), Usuário de Consulta (somente leitura) e Administrador Técnico (configurações gerais)

## 5. Estrutura de arquivos
```
saa/
├── src/
│   ├── controllers/
│   │   ├── grade_controller.py
│   │   ├── sala_controller.py
│   │   ├── restricao_controller.py
│   │   ├── alocacao_controller.py
│   │   └── dashboard_controller.py
│   ├── providers/
│   │   ├── interfaces/
│   │   │   ├── grade_provider_interface.py
│   │   │   ├── sala_provider_interface.py
│   │   │   ├── restricao_provider_interface.py
│   │   │   ├── alocacao_provider_interface.py
│   │   │   └── dashboard_provider_interface.py
│   │   ├── implementations/
│   │   │   ├── grade_csv_provider.py
│   │   │   ├── sala_csv_provider.py
│   │   │   ├── restricao_csv_provider.py
│   │   │   ├── alocacao_csv_provider.py
│   │   │   └── dashboard_csv_provider.py
│   ├── routers/
│   │   ├── grade.py
│   │   ├── sala.py
│   │   ├── restricao.py
│   │   ├── alocacao.py
│   │   └── dashboard.py
├── frontend/
│   ├── src/
│   │   ├── views/
│   │   │   ├── DashboardSAA.vue
│   │   │   ├── Grades.vue
│   │   │   ├── Salas.vue
│   │   │   ├── Alocacoes.vue
│   │   │   └── Conflitos.vue
│   │   ├── stores/
│   │   │   ├── grade.ts
│   │   │   ├── sala.ts
│   │   │   ├── alocacao.ts
│   │   │   └── dashboard.ts
│   │   ├── router/
│   │   │   └── index.ts
│   │   └── services/
│   │       └── api.ts
```

## 6. Guardrails para IA (SDD)
Para manter a integridade sistêmica, os assistentes de IA devem aderir às seguintes restrições:

### Escopo Positivo (O que fazer)
- Comentar funções complexas seguindo o padrão JSDoc/TSDoc.
- Utilizar blocos try-catch com logs de erro padronizados.
- Criar um arquivo de teste `.spec.ts` para cada novo controller ou service.
- O Controller concentra validações e lógica de negócio.
- O Provider lê a fonte de dados (CSV no MVP).
- O Frontend apenas consome a API.

### Escopo Negativo (O que NÃO fazer - Anti-Patterns)
- Proibido o uso de `DELETE` SQL. Utilizar coluna `deleted_at`.
- Proibido salvar chaves de API ou senhas no código; utilizar `.env`.
- Não alterar arquivos de infraestrutura ou configuração global sem instrução explícita no `SPEC.md`.
- A alocação automática e o motor de otimização ficam fora do escopo do MVP.
- O Router não deve conter regra de negócio.
- A lógica de conflitos não deve ficar no frontend.
- O MVP não deve acessar diretamente o AGHU nem realizar escrita de dados nele.