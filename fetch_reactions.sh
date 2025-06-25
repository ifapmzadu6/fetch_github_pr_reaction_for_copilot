#!/bin/bash

# --- 設定 ---
# 集計期間 (YYYY-MM-DD形式)
START_DATE="2025-05-01"
END_DATE="2025-06-26"

# Copilotのユーザー名
COPILOT_USER="github-actions[bot]"

# --- スクリプト本体 ---

if [ "$#" -eq 0 ]; then
  echo "エラー: 1つ以上のリポジトリを引数に指定してください (例: owner/repo)" >&2
  exit 1
fi

# ヘッダー出力
echo "date,repository,points"

# リアクションを処理してCSV形式で出力する内部関数
process_reactions() {
  local item=$1
  local repo=$2
  local reactions_url
  reactions_url=$(echo "$item" | jq -r '.reactions.url')

  if [ -z "$reactions_url" ] || [ "$reactions_url" == "null" ]; then
    return
  fi

  gh api "$reactions_url" | jq -c '.[]' | while IFS= read -r reaction; do
    local content
    content=$(echo "$reaction" | jq -r '.content')
    local created_at
    created_at=$(echo "$reaction" | jq -r '.created_at' | cut -d'T' -f1)
    
    local points=0
    case "$content" in
      "+1") points=3 ;;
      "hooray" | "heart") points=2 ;;
      "rocket" | "laugh") points=1 ;;
      "confused") points=-1 ;;
      "-1") points=-2 ;;
      *) points=0 ;;
    esac
    
    echo "$created_at,$repo,$points"
  done
}

# 引数で渡された全リポジトリをループ
for repo in "$@"; do
  # --- 対象PRの特定 (期間検索) ---
  pr_numbers=$(gh pr list -R "$repo" --search "created:$START_DATE..$END_DATE" --json number --jq '.[]?.number')

  for pr_number in $pr_numbers; do
    if [ -z "$pr_number" ]; then
      continue
    fi
    
    # --- Copilotユーザーでのフィルタリング ---
    JQ_FILTER=".[] | select(.user.login == \"$COPILOT_USER\")"

    # 1. Issue形式のコメント (PRへの総合的なコメント)
    gh api "repos/$repo/issues/$pr_number/comments?per_page=100" | \
    jq -c "$JQ_FILTER" | \
    while IFS= read -r comment; do
      process_reactions "$comment" "$repo"
    done

    # 2. レビューコメント (コード行へのコメント)
    gh api "repos/$repo/pulls/$pr_number/comments?per_page=100" | \
    jq -c "$JQ_FILTER" | \
    while IFS= read -r comment; do
      process_reactions "$comment" "$repo"
    done

    # 3. レビュー本体 (複数のコメントをまとめたレビュー)
    gh api "repos/$repo/pulls/$pr_number/reviews?per_page=100" | \
    jq -c "$JQ_FILTER" | \
    while IFS= read -r review; do
      # .bodyが空でないもののみ対象
      if echo "$review" | jq -e '.body != null and .body != ""' > /dev/null; then
        process_reactions "$review" "$repo"
      fi
    done
  done
done
