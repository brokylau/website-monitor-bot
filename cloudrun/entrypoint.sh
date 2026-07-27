#!/usr/bin/env bash

set -Eeuo pipefail

echo "=========================================="
echo "PLAUD page monitor started"
echo "Time: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "Cloud Run execution: ${CLOUD_RUN_EXECUTION:-unknown}"
echo "=========================================="

# 必需参数检查
: "${GITHUB_REPOSITORY:?GITHUB_REPOSITORY is required}"
: "${GITHUB_USERNAME:?GITHUB_USERNAME is required}"
: "${GITHUB_TOKEN:?GITHUB_TOKEN is required}"
: "${FEISHU_WEBHOOK:?FEISHU_WEBHOOK is required}"

GITHUB_BRANCH="${GITHUB_BRANCH:-main}"
MONITOR_SCRIPT="${MONITOR_SCRIPT:-monitor.py}"
AIHOT_STATE_FILE="${AIHOT_STATE_FILE:-aihot_state.json}"

REPO_DIR="/workspace/repo"

export GIT_TERMINAL_PROMPT=0
export GIT_ASKPASS="/app/git-askpass.sh"

echo "Repository: ${GITHUB_REPOSITORY}"
echo "Branch: ${GITHUB_BRANCH}"
echo "Python script: ${MONITOR_SCRIPT}"

# 每次运行使用干净的仓库副本
rm -rf "${REPO_DIR}"

echo "Cloning repository..."

git clone \
  --depth 1 \
  --branch "${GITHUB_BRANCH}" \
  "https://github.com/${GITHUB_REPOSITORY}.git" \
  "${REPO_DIR}"

cd "${REPO_DIR}"

if [[ ! -f "${MONITOR_SCRIPT}" ]]; then
  echo "ERROR: Python script does not exist: ${MONITOR_SCRIPT}"
  echo "Current repository files:"
  find . -maxdepth 2 -type f | sort
  exit 1
fi

echo "Running Python monitor..."

# 即使 Python 返回失败，仍尝试提交已经生成的截图和状态文件
set +e
python "${MONITOR_SCRIPT}"
PYTHON_EXIT_CODE=$?
set -e

echo "Python exit code: ${PYTHON_EXIT_CODE}"

git config user.name "Plaud Cloud Run Monitor"
git config user.email "plaud-cloud-run-monitor@users.noreply.github.com"

# 新增截图和删除的旧截图都要提交
if [[ -d "screenshots" ]]; then
  git add -A screenshots
fi

# 提交 AI HOT RSS 断点
if [[ -f "${AIHOT_STATE_FILE}" ]]; then
  git add "${AIHOT_STATE_FILE}"
fi

if git diff --cached --quiet; then
  echo "No screenshot or state changes to commit."
else
  echo "Committing generated files..."

  git commit -m "chore: update monitor screenshots $(date '+%Y-%m-%d %H:%M:%S')"

  # 防止运行期间远端刚好发生新提交
  git pull --rebase origin "${GITHUB_BRANCH}"

  git push origin "HEAD:${GITHUB_BRANCH}"

  echo "Screenshots and state pushed to GitHub."
fi

echo "=========================================="
echo "PLAUD page monitor completed"
echo "Time: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "=========================================="

exit "${PYTHON_EXIT_CODE}"
