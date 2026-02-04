# Automação de fluxo com Playwright

Este guia descreve como executar o script de automação com Playwright, usando
variáveis de ambiente para definir o fluxo.

## ✅ Pré-requisitos

```bash
pip install playwright
python -m playwright install
```

## ▶️ Execução rápida

```bash
export WORKFLOW_BASE_URL="https://exemplo.com"
export WORKFLOW_USERNAME="seu_usuario"
export WORKFLOW_PASSWORD="sua_senha"
export WORKFLOW_USERNAME_SELECTOR="#username"
export WORKFLOW_PASSWORD_SELECTOR="#password"
export WORKFLOW_SUBMIT_SELECTOR="button[type='submit']"
export WORKFLOW_POST_LOGIN_SELECTOR=".dashboard"
export WORKFLOW_NAV_SELECTOR=".menu-item"
export WORKFLOW_NAV_WAIT_SELECTOR=".destino"
export WORKFLOW_SCREENSHOT_PATH="reports/workflow.png"

python scripts/playwright_workflow.py
```

## Variáveis de ambiente suportadas

- `WORKFLOW_BASE_URL` (obrigatória): URL inicial do fluxo.
- `WORKFLOW_HEADLESS`: controla o modo headless (`true`/`false`). Default: `true`.
- `WORKFLOW_USERNAME` / `WORKFLOW_PASSWORD`: credenciais para login.
- `WORKFLOW_USERNAME_SELECTOR`: seletor do campo de usuário.
- `WORKFLOW_PASSWORD_SELECTOR`: seletor do campo de senha.
- `WORKFLOW_SUBMIT_SELECTOR`: seletor do botão de login.
- `WORKFLOW_POST_LOGIN_SELECTOR`: seletor para validar o login concluído.
- `WORKFLOW_NAV_SELECTOR`: seletor para navegação adicional após login.
- `WORKFLOW_NAV_WAIT_SELECTOR`: seletor de confirmação da navegação.
- `WORKFLOW_SCREENSHOT_PATH`: caminho para salvar screenshot.

## Observações

- Ajuste os seletores para o HTML real do fluxo.
- Se não houver login ou navegação adicional, deixe os seletores vazios.
- Para depuração visual, defina `WORKFLOW_HEADLESS=false`.
