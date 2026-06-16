# Guia de Instalação e Execução

Este guia contém os passos detalhados para configurar e executar os ambientes de desenvolvimento do backend e do frontend.

## Pré-requisitos

- Python 3.10 ou superior
- Node.js 18 ou superior (recomendado via NVM)
- Git

### Dependências do Sistema (Ubuntu/Debian)
O projeto utiliza bibliotecas modernas que minimizam a necessidade de pacotes do sistema. No entanto, o `build-essential` e o `git` são recomendados:
```bash
sudo apt update && sudo apt install -y build-essential git
```

## 1. Configuração do Backend

Siga estes passos a partir da raiz do repositório. O projeto utiliza o **uv** para gerenciamento ultra-rápido de pacotes e ambientes.

```bash
# 1. Instale o uv (caso não possua)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Sincronize o ambiente e dependências
uv sync

# 3. Configure as variáveis de ambiente
cp .env.example .env

# Edite o arquivo .env com suas configurações
# Dica: Para desenvolvimento offline, use PACIENTE_PROVIDER_TYPE=CSV
nano .env
```

## 2. Configuração do Frontend

Estes passos devem ser executados em um novo terminal.

```bash
# 1. Navegue até a pasta do frontend
cd frontend

# 2. Instale as dependências e execute
npm install
npm run dev
```

## 3. Executando a Aplicação

O projeto oferece dois modos principais de execução através de scripts automatizados na raiz:

### A. Modo de Desenvolvimento (`./dev.sh`) - RECOMENDADO
Inicia o Backend (FastAPI) e o Frontend (Vite) em paralelo.
- **Vantagem:** Hot Module Replacement (HMR). Alterações no frontend aparecem instantaneamente.
- **Porta Frontend:** `http://localhost:5173`
- **Porta Backend:** `http://localhost:8000`

```bash
chmod +x dev.sh
./dev.sh
```

### B. Modo Produção Local (`./start.sh`)
Realiza o build completo do frontend e serve tudo através do FastAPI.
- **Vantagem:** Simula exatamente o comportamento de produção.
- **Porta Única:** `http://localhost:8000`

```bash
chmod +x start.sh
./start.sh
```

---

## 4. Comandos Manuais (Troubleshooting)

Caso precise executar partes isoladas ou depurar:

**Backend isolado:**
```bash
uv run uvicorn src.main:app --reload
```

**Frontend isolado:**
```bash
cd frontend
npm run dev
```

**Gerar Build Manual:**
```bash
cd frontend
npm run build
```
