# run_evolve.ps1 — Run OpenEvolve on AgentSociety CrewAI main project
# Usage: .\run_evolve.ps1

Set-Location $PSScriptRoot

# NVIDIA NIM — used by OpenEvolve mutation LLM (model 0) and CrewAI agents
$env:OPENAI_API_KEY   = "nvapi-your-nvidia-api-key-here"
$env:OPENAI_API_BASE  = "https://integrate.api.nvidia.com/v1"
$env:NVIDIA_API_KEY   = "nvapi-your-nvidia-api-key-here"
$env:LLAMA_API_KEY    = "nvapi-your-nvidia-api-key-here"

# Groq fallback accounts — used by OpenEvolve mutation LLM (models 1 and 2)
# Circular order: NVIDIA -> Groq account 1 -> Groq account 2 -> NVIDIA ...
$env:GROQ_API_KEY     = "gsk_your-groq-api-key-1-here"
$env:GROQ_API_KEY_2   = "gsk_your-groq-api-key-2-here"

# Suppress noisy logs
$env:LITELLM_LOG      = "ERROR"
$env:PYTHONUTF8       = "1"

# Evaluate 1 task per iteration (fast; professor's requirement)
$env:OPENEVOLVE_NUM_TASKS = "1"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " OpenEvolve - AgentSociety Final Project" -ForegroundColor Cyan
Write-Host " 50 iterations / 3 islands / 1 task"     -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

uv run python -m openevolve.cli `
    config/agents_evolving.yaml `
    openevolve_evaluator.py `
    --config config/openevolve_config.yaml `
    --output config/openevolve_output `
    --iterations 50
