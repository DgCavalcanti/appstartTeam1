# 🧪 Guia de Testes de Integração - Alocação Automática

## Pré-requisitos

1. ✅ Backend FastAPI rodando em `http://localhost:8000`
2. ✅ Frontend Vue rodando em `http://localhost:5173` (ou similar)
3. ✅ Token JWT válido (obtido via login)
4. ✅ Dados de teste: Grades, Salas, Restrições importadas

---

## 📋 Roteiro de Testes End-to-End

### Test 1: Fluxo Completo de Alocação Automática

**Objetivo:** Validar o fluxo completo desde seleção até exibição de resultado

**Passos:**

```
1. Abrir Dashboard → /saa/alocacao-automatica
   ✓ Deve exibir título "Dashboard de Alocação Automática"
   ✓ Deve exibir formulário com campos: Dia, Turno
   ✓ Deve exibir indicadores gerais (salas, conflitos)

2. Selecionar Segunda + Manhã
   ✓ Botão "Executar Alocação" deve ser habilitado
   ✓ Campo de erro deve estar vazio

3. Clicar "Executar Alocação"
   ✓ Botão deve mostrar "⏳ Processando..."
   ✓ Nenhuma interação deve ser possível enquanto processa

4. Após receber resposta
   ✓ Resultado deve aparecer com métricas:
     - Quantidade de alocações criadas
     - Quantidade de grades não alocadas
     - Quantidade de conflitos detectados
   ✓ Tabela de alocações deve mostrar:
     - Grade ID, Sala ID, Especialidade, Profissional, Status
   ✓ Se houver grades não alocadas:
     - Tabela com especialidade, profissional, dia, turno, qtd_salas
   ✓ Se houver conflitos:
     - Cards com tipo, gravidade, descrição
     - Cores diferentes por gravidade (crítico=vermelho, operacional=laranja)
```

**Validação:**
```bash
# Backend deve receber POST /api/alocacoes/automatica
# com payload:
{
  "dia_semana": "Segunda",
  "turno": "Manhã"
}

# Response esperada:
{
  "alocacoes_criadas": [...],
  "grades_nao_alocadas": [...],
  "resumo": "X alocações criadas, Y grades não alocadas"
}
```

---

### Test 2: Sincronização com Store Pinia

**Objetivo:** Verificar se alocações são sincronizadas corretamente no estado frontend

**Passos:**

```
1. Abrir DevTools → Vue (Pinia)
2. Executar alocação automática
3. Verificar em store.saa.alocacoes:
   ✓ Novas alocações devem ser adicionadas
   ✓ Alocações antigas do mesmo dia/turno devem ser removidas
   ✓ Alocações de outro dia/turno devem ser preservadas
4. Verificar em store.saa.conflitos:
   ✓ Conflitos devem ser recalculados automaticamente
   ✓ Motor detecta duplicatas, salas indisponíveis, etc.
```

---

### Test 3: Tratamento de Erros

**Objetivo:** Validar tratamento de erros na API

**Passos:**

```
1. Parar o backend (simular indisponibilidade)
2. Tentar executar alocação
   ✓ Deve exibir erro visível: "❌ Erro: ..."
   ✓ Botão deve voltara ser clicável
   ✓ Nenhum resultado parcial deve aparecer

2. Retomar backend com dados inválidos
3. Enviar POST /api/alocacoes/automatica com dados ruins
   ✓ Erro da API deve ser exibido corretamente
   ✓ User não fica travado
```

---

### Test 4: Autenticação

**Objetivo:** Validar que token JWT é passado corretamente

**Passos:**

```
1. Abrir DevTools → Network
2. Executar alocação automática
3. Verificar requisição para POST /api/alocacoes/automatica:
   ✓ Header "Authorization: Bearer <token>" deve estar presente
   ✓ Content-Type deve ser "application/json"
   ✓ Body deve conter dia_semana e turno

4. Remover token de localStorage
5. Tentar executar alocação
   ✓ Erro: "Token de autenticação não encontrado"
```

---

### Test 5: Indicadores Gerais

**Objetivo:** Validar atualização de indicadores

**Passos:**

```
1. Na seção "Indicadores Gerais":
   ✓ Total de salas deve corresponder ao store
   ✓ Salas disponíveis deve ser count(status='disponivel')
   ✓ Salas bloqueadas deve ser count(status='bloqueada')
   ✓ Conflitos críticos deve ser count(gravidade='critico')

2. Após alocação automática:
   ✓ Indicadores devem atualizar se o resultado criou conflitos
```

---

### Test 6: Conflitos Detectados

**Objetivo:** Validar exibição de conflitos

**Passos:**

```
1. Executar alocação que gera conflitos
   ✓ Seção de conflitos deve aparecer
   ✓ Cada conflito deve mostrar:
     - Tipo: "sala_indisponivel", "dupla_alocacao", etc
     - Gravidade: com badge colorida (🔴 crítico, 🟠 operacional, 🔵 info)
     - Descrição: detalhamento do conflito

2. Cores devem corresponder:
   - Crítico: fundo vermelho claro (#fee), badge vermelho
   - Operacional: fundo laranja claro (#fff3e0), badge laranja
   - Info: fundo azul claro (#e3f2fd), badge azul
```

---

### Test 7: Navegação

**Objetivo:** Validar que o link aparece no menu

**Passos:**

```
1. Abrir sidebar
   ✓ Deve haver link "Alocação Automática" com ícone ✨
   ✓ Deve estar no grupo de links SAA
   ✓ Estar entre "Alocações" e "Importar CSV"

2. Clicar no link
   ✓ Deve navegar para /saa/alocacao-automatica
   ✓ Componente DashboardAlocacao deve aparecer
```

---

## 🧬 Testes de Unidade

### Store (saa.ts)

```bash
npm run test -- saa.spec.ts
```

**Deve testar:**
- ✅ `executarAlocacaoAutomatica` com sucesso
- ✅ `executarAlocacaoAutomatica` com erro
- ✅ Sincronização de alocações
- ✅ Recálculo automático de conflitos
- ✅ Passagem de token na requisição

### Componente (DashboardAlocacao.vue)

```bash
npm run test -- DashboardAlocacao.spec.ts
```

**Deve testar:**
- ✅ Renderização do formulário
- ✅ Habilitação/desabilitação do botão
- ✅ Exibição de resultado
- ✅ Tratamento de erros
- ✅ Limpeza após nova tentativa

---

## 📊 Checklist de Cobertura

| Recurso | Testes | Status |
|---------|--------|--------|
| Store `executarAlocacaoAutomatica` | Unit | ✅ |
| Store sincronização | Unit | ✅ |
| Componente renderização | Unit | ✅ |
| Componente interação | Unit | ✅ |
| E2E fluxo completo | Integration | 📋 |
| E2E tratamento erro | Integration | 📋 |
| API autenticação | Integration | 📋 |
| Conflitos detectados | Integration | 📋 |

---

## 🚀 Comando para Rodar Tudo

```bash
# Rodar testes de unidade
npm run test

# Rodar com cobertura
npm run test -- --coverage

# Watch mode para desenvolvimento
npm run test -- --watch
```

---

## 🔗 Links Úteis

- **API Docs:** `http://localhost:8000/docs`
- **Frontend:** `http://localhost:5173/saa/alocacao-automatica`
- **DevTools Vue:** F12 → Vue Tab
- **Pinia DevTools:** F12 → Pinia Tab
