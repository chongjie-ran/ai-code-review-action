#!/usr/bin/env python3
"""
CodeLens AI GitHub Action - Entrypoint
Handles PR scanning and GitHub API interaction
"""
import os
import sys
import json
import subprocess
import requests

GITHUB_API = "https://api.github.com"


def github_request(method: str, path: str, token: str, **kwargs):
    """Make authenticated GitHub API request"""
    url = f"{GITHUB_API}{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "CodeLens-Action/1.0",
    }
    resp = requests.request(method, url, headers=headers, **kwargs, timeout=30)
    resp.raise_for_status()
    return resp.json()


def get_changed_files(token: str, owner: str, repo: str, base: str, head: str):
    """Get list of changed files between base and head branches"""
    url = f"{GITHUB_API}/repos/{owner}/{repo}/compare/{base}...{head}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return [f for f in data.get("files", []) if f.get("status") != "removed"]


def get_file_content(token: str, owner: str, repo: str, path: str, ref: str) -> str:
    """Get file content at specific ref"""
    url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    params = {"ref": ref}
    resp = requests.get(url, headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    import base64
    return base64.b64decode(data["content"]).decode("utf-8", errors="replace")


def get_pr_info(token: str, owner: str, repo: str, pr_number: int) -> dict:
    """Get PR details"""
    return github_request(
        "GET",
        f"/repos/{owner}/{repo}/pulls/{pr_number}",
        token,
    )


def get_files_in_pr(token: str, owner: str, repo: str, pr_number: int) -> list:
    """Get files changed in a PR"""
    return github_request(
        "GET",
        f"/repos/{owner}/{repo}/pulls/{pr_number}/files",
        token,
    )


def scan_code(api_key: str, api_url: str, files: list[dict]) -> dict:
    """Send files to CodeLens API for analysis"""
    payload = {"files": files}
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    resp = requests.post(
        f"{api_url}/api/v1/review-pr",
        headers=headers,
        json=payload,
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()


def post_pr_comment(token: str, owner: str, repo: str, pr_number: int, body: str, comment_id: int = None):
    """Post or update PR comment"""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    if comment_id:
        url = f"{GITHUB_API}/repos/{owner}/{repo}/issues/comments/{comment_id}"
        requests.patch(url, headers=headers, json={"body": body}, timeout=30)
    else:
        url = f"{GITHUB_API}/repos/{owner}/{repo}/issues/{pr_number}/comments"
        requests.post(url, headers=headers, json={"body": body}, timeout=30)


def find_existing_comment(token: str, owner: str, repo: str, pr_number: int) -> int:
    """Find existing CodeLens comment ID"""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    url = f"{GITHUB_API}/repos/{owner}/{repo}/issues/{pr_number}/comments"
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    for comment in resp.json():
        if "🤖 CodeLens AI 代码审查报告" in comment.get("body", ""):
            return comment["id"]
    return None


def generate_comment(score: int, high: int, medium: int, low: int, total: int, pr_title: str, base_branch: str, api_url: str) -> str:
    """Generate PR comment body"""
    score_emoji = "🟢" if score >= 90 else "🟡" if score >= 70 else "🟠" if score >= 50 else "🔴"
    gate_passed = high == 0

    gate_text = "✅ **PASSED** - No high severity issues" if gate_passed else "❌ **BLOCKED** - High severity issues found"

    return f"""## 🤖 CodeLens AI 代码审查报告

**扫描完成** · `{pr_title}` → `main`

---

### 📊 质量评分

| 指标 | 数值 |
|------|------|
| **总分** | {score_emoji} **{score}/100** |
| 🔴 高危 | **{high}** |
| 🟡 中危 | **{medium}** |
| 🟢 低危 | **{low}** |
| **合计** | **{total}** |

### 🚦 Quality Gate

{gate_text}

> {'代码质量达标，可以合并 ✅' if gate_passed else '发现高危问题，请修复后再合并 ⚠️'}

---

### 📋 详细报告

查看完整HTML报告：[{api_url}/dashboard]({api_url}/dashboard)

---

*🤖 由 **CodeLens AI** 提供 · [申请API Key](https://github.com/chongjie-ran/ai-code-review-action)*"""


def main():
    # Parse inputs
    # Note: GITHUB_TOKEN and PR context available via env vars in GitHub Actions
    github_token = os.environ.get("GITHUB_TOKEN", "")
    api_key = os.environ.get("CODELENS_API_KEY", "")
    api_url = os.environ.get("CODELENS_API_URL", "https://api.codelens.ai").rstrip("/")
    min_score = int(os.environ.get("MIN_SCORE", "0"))
    fail_on_high = os.environ.get("FAIL_ON_HIGH", "false").lower() == "true"

    # GitHub context from environment
    owner = os.environ.get("GITHUB_REPOSITORY_OWNER", "")
    repo_name = os.environ.get("GITHUB_REPOSITORY", "").split("/")[-1] if "/" in os.environ.get("GITHUB_REPOSITORY", "") else ""
    pr_number = int(os.environ.get("PR_NUMBER", os.environ.get("GITHUB_PR_NUMBER", "0")))
    head_sha = os.environ.get("GITHUB_SHA", "")
    base_branch = os.environ.get("GITHUB_BASE_REF", "main")

    # Also accept as positional args (for Dockerfile-based runs without env vars)
    if len(sys.argv) > 1 and sys.argv[1]:
        github_token = sys.argv[1]
    if len(sys.argv) > 2 and sys.argv[2]:
        api_key = sys.argv[2]
    if len(sys.argv) > 3 and sys.argv[3]:
        api_url = sys.argv[3].rstrip("/")
    if len(sys.argv) > 4 and sys.argv[4]:
        min_score = int(sys.argv[4])
    if len(sys.argv) > 5 and sys.argv[5]:
        pr_number_override = int(sys.argv[5])
        if pr_number_override > 0:
            pr_number = pr_number_override
    if len(sys.argv) > 6 and sys.argv[6]:
        fail_on_high = sys.argv[6].lower() == "true"

    print(f"CodeLens AI Action starting...")
    print(f"  API URL: {api_url}")
    print(f"  PR: #{pr_number}")
    print(f"  Base: {base_branch}")

    if not api_key:
        print("ERROR: CODELENS_API_KEY not set")
        sys.exit(1)

    if not pr_number:
        print("No PR found, skipping review")
        sys.exit(0)

    # Get PR info
    pr = get_pr_info(github_token, owner, repo_name, pr_number)
    pr_title = pr.get("title", "Unknown PR")
    head_branch = pr.get("head", {}).get("ref", "")
    head_sha = pr.get("head", {}).get("sha", head_sha)
    base_branch = pr.get("base", {}).get("ref", base_branch)

    print(f"  PR: #{pr_number} - {pr_title}")
    print(f"  Branch: {head_branch} -> {base_branch}")

    # Get changed files
    print("Fetching changed files...")
    changed_files = get_files_in_pr(github_token, owner, repo_name, pr_number)
    print(f"  {len(changed_files)} files changed")

    # Build scan payload
    files_to_scan = []
    ext_to_lang = {
        "py": "python", "js": "javascript", "ts": "typescript",
        "jsx": "typescript", "tsx": "typescript", "java": "java",
        "go": "go", "rs": "rust", "rb": "ruby", "php": "php",
    }

    for f in changed_files[:50]:  # Limit to 50 files
        path = f["filename"]
        ext = path.rsplit(".", 1)[-1] if "." in path else ""
        lang = ext_to_lang.get(ext, None)
        if not lang:
            continue

        content = get_file_content(github_token, owner, repo_name, path, head_sha)
        if len(content) > 500_000:  # Skip files > 500KB
            print(f"  Skipping large file: {path} ({len(content)} bytes)")
            continue

        files_to_scan.append({
            "path": path,
            "language": lang,
            "content": content[:100_000],  # Truncate to 100KB per file
        })

    print(f"  {len(files_to_scan)} files queued for scan")

    if not files_to_scan:
        print("No scannable files found")
        sys.exit(0)

    # Scan
    print("Scanning code with CodeLens AI...")
    try:
        result = scan_code(api_key, api_url, files_to_scan)
    except requests.exceptions.RequestException as e:
        print(f"ERROR: CodeLens API request failed: {e}")
        sys.exit(1)

    score = result.get("score", 100)
    summary = result.get("summary", {})
    high = summary.get("high", 0)
    medium = summary.get("medium", 0)
    low = summary.get("low", 0)
    total = summary.get("total", 0)
    session_id = result.get("session_id", "")

    print(f"  Score: {score}/100")
    print(f"  Issues: {high}H / {medium}M / {low}L / {total} total")

    # Quality gate
    gate_passed = high == 0 and score >= min_score

    # Post comment
    print("Posting PR comment...")
    comment_id = find_existing_comment(github_token, owner, repo_name, pr_number)
    body = generate_comment(score, high, medium, low, total, pr_title, base_branch, api_url)
    post_pr_comment(github_token, owner, repo_name, pr_number, body, comment_id)
    print(f"  Comment {'updated' if comment_id else 'created'}")

    # Output for GitHub Actions
    print(f"::set-output name=score::{score}", flush=True)
    print(f"::set-output name=high::{high}", flush=True)
    print(f"::set-output name=medium::{medium}", flush=True)
    print(f"::set-output name=low::{low}", flush=True)
    print(f"::set-output name=quality-gate::{'pass' if gate_passed else 'fail'}", flush=True)

    # Exit code
    if fail_on_high and high > 0:
        print(f"\n❌ Quality gate FAILED - {high} high-severity issues found")
        sys.exit(1)
    elif score < min_score:
        print(f"\n⚠️  Score {score} below minimum {min_score}")
        sys.exit(1)
    else:
        print(f"\n✅ Code review complete")
        sys.exit(0)


if __name__ == "__main__":
    main()
