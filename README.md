# CodeLens AI GitHub Action

AI-powered code review for your pull requests. Detects security vulnerabilities, logic errors, and tech debt.

## Features

- 🔴 **Security**: Detects API key leaks, SQL injection, command injection, hardcoded credentials
- 🧠 **Logic**: Finds null pointers, index out of bounds, type mismatches
- 📉 **Tech Debt**: Identifies TODO comments, debug code, duplicate logic
- 🌐 **Multi-language**: Python, JavaScript, TypeScript, Go, Rust, Java
- 💬 **PR Comments**: Posts detailed review report as PR comment
- 🚦 **Quality Gate**: Optionally blocks PR merge on high-severity issues

## Usage

### 1. Get Your API Key

Sign up at [codelens.ai](https://codelens.ai) and get your API key.

### 2. Add to Your Workflow

Create `.github/workflows/codelens.yml`:

```yaml
name: CodeLens AI Code Review

on:
  pull_request:
    branches: [main, master, develop]
  push:
    branches: [main, master]

jobs:
  codelens-review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: CodeLens AI Review
        uses: chongjie-ran/ai-code-review-action@v1.1
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          codelens-api-key: ${{ secrets.CODELENS_API_KEY }}
          codelens-api-url: https://api.codelens.ai  # optional, or your self-hosted URL
          fail-on-high: true
          min-score: 70
```

### 3. Add Secrets

In your GitHub repo: **Settings → Secrets → Actions**

| Secret | Value |
|--------|-------|
| `CODELENS_API_KEY` | Your CodeLens API key |

### 4. That's It! 🎉

Every PR will automatically get an AI code review comment.

## Self-Hosted Backend

If you're running your own CodeLens backend:

```yaml
- name: CodeLens AI Review
  uses: chongjie-ran/ai-code-review-action@v1.1
  with:
    github-token: ${{ secrets.GITHUB_TOKEN }}
    codelens-api-key: ${{ secrets.CODELENS_API_KEY }}
    codelens-api-url: https://your-codelens-server.com
```

## Configuration

| Input | Description | Default |
|-------|-------------|---------|
| `github-token` | GitHub token for API access | Required |
| `codelens-api-key` | Your CodeLens API key | Required |
| `codelens-api-url` | CodeLens backend URL | `https://api.codelens.ai` |
| `fail-on-high` | Fail workflow on high-severity | `false` |
| `min-score` | Minimum quality score (0-100) | `0` |

## Output

| Output | Description |
|--------|-------------|
| `score` | Code quality score (0-100) |
| `high` | High-severity issues |
| `medium` | Medium-severity issues |
| `low` | Low-severity issues |
| `quality-gate` | `pass` or `fail` |

## Docker

```bash
docker run \
  -e GITHUB_TOKEN=ghp_xxx \
  -e CODELENS_API_KEY=xxx \
  chongjie-ran/codelens-action:latest
```
