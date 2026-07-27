#!/usr/bin/env bash

set -Eeuo pipefail

echo "=========================================="
echo "PLAUD page monitor started"
echo "Time: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "Cloud Run execution: ${CLOUD_RUN_EXECUTION:-unknown}"
echo "=========================================="

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

rm -rf "${REPO_DIR}"

echo "Creating partial Git clone..."

# 只下载 Git 元数据，不下载 screenshots 中的大量图片
git clone \
  --depth 1 \
  --filter=blob:none \
  --no-checkout \
  --branch "${GITHUB_BRANCH}" \
  "https://github.com/${GITHUB_REPOSITORY}.git" \
  "${REPO_DIR}"

cd "${REPO_DIR}"

# 只检出程序和 RSS 状态文件
git sparse-checkout init --no-cone

git sparse-checkout set --no-cone \
  "/${MONITOR_SCRIPT}" \
  "/${AIHOT_STATE_FILE}"

git checkout "${GITHUB_BRANCH}"

if [[ ! -f "${MONITOR_SCRIPT}" ]]; then
  echo "ERROR: Python script does not exist: ${MONITOR_SCRIPT}"
  exit 1
fi

# 不下载历史截图，只为本次任务创建空目录
mkdir -p screenshots

echo "Running Python monitor..."

# 即使部分页面抓取失败，也尝试上传已经生成的文件
set +e
python "${MONITOR_SCRIPT}"
PYTHON_EXIT_CODE=$?
set -e

echo "Python exit code: ${PYTHON_EXIT_CODE}"

git config user.name "Plaud Cloud Run Monitor"
git config user.email "plaud-cloud-run-monitor@users.noreply.github.com"

# screenshots 位于 sparse checkout 范围外，因此需要 --sparse 和 -f
if [[ -d "screenshots" ]]; then
  git add --sparse -f -- screenshots
fi

if [[ -f "${AIHOT_STATE_FILE}" ]]; then
  git add -f -- "${AIHOT_STATE_FILE}"
fi

echo "Git changes:"
git status --short

if git diff --cached --quiet; then
  echo "No screenshot or state changes to commit."
else
  git commit \
    -m "chore: update monitor screenshots $(date '+%Y-%m-%d %H:%M:%S')"

  git push origin "HEAD:${GITHUB_BRANCH}"

  echo "Screenshots and state pushed to GitHub."
fi

echo "=========================================="
echo "PLAUD page monitor completed"
echo "Time: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "=========================================="

exit "${PYTHON_EXIT_CODE}"
