#!/bin/bash

# --- 設定 ---
START_DATE="2025-05-01"
END_DATE="2025-06-26"
COPILOT_USER="github-actions[bot]"

# --- 関数定義 ---

# サマリーを表示する関数
show_summary_from_data() {
  local data=$1
  if [ -z "$data" ]; then
    echo "No data to summarize."
    return
  fi

  echo "--- Daily Summary ---"
  daily_summary=$(echo "$data" | awk -F, 'NR>1 {count[$1]++; sum[$1]+=$3} END {for (d in sum) {printf "%-13s | %-9d | %-12d | %.2f\n", d, count[d], sum[d], sum[d]/count[d]}}' | sort -k1)
  echo -e "Date          | Reactions | Total Points | Average Points\n--------------|-----------|--------------|----------------\n$daily_summary"

  echo ""
  echo "--- Weekly Summary ---"
  weekly_summary=$(echo "$data" | awk -F, 'NR>1 {cmd="date -j -f %Y-%m-%d "$1" +%Y-%V"; cmd|getline w; close(cmd); count[w]++; sum[w]+=$3} END {for (w in sum) {printf "%-13s | %-9d | %-12d | %.2f\n", w, count[w], sum[w], sum[w]/count[w]}}' | sort -k1)
  echo -e "Week          | Reactions | Total Points | Average Points\n--------------|-----------|--------------|----------------\n$weekly_summary"
}

# リアクションを収集する関数
fetch_reactions() {
  local fetch_all_users=$1
  shift
  local repos=("$@")

  for repo in "${repos[@]}"; do
    gh pr list -R "$repo" --search "created:$START_DATE..$END_DATE" --json number --jq '.[] | .number' | while read -r pr_number; do
      if [ -z "$pr_number" ]; then continue; fi
      
      local JQ_FILTER
      if [ "$fetch_all_users" = true ]; then
        JQ_FILTER=".[]"
      else
        JQ_FILTER=".[] | select(.user.login == \"$COPILOT_USER\")"
      fi

      # 各APIからリアクションを処理
      gh api "repos/$repo/issues/$pr_number/comments?per_page=100" | jq -c "$JQ_FILTER" | while IFS= read -r c; do process_single_reaction "$c" "$repo"; done
      gh api "repos/$repo/pulls/$pr_number/comments?per_page=100" | jq -c "$JQ_FILTER" | while IFS= read -r c; do process_single_reaction "$c" "$repo"; done
      gh api "repos/$repo/pulls/$pr_number/reviews?per_page=100" | jq -c "$JQ_FILTER" | while IFS= read -r r; do if echo "$r" | jq -e '.body != null and .body != ""' > /dev/null; then process_single_reaction "$r" "$repo"; fi; done
    done
  done
}

# 個々のリアクションをポイントに変換する関数
process_single_reaction() {
  local item=$1; local repo=$2
  local reactions_url=$(echo "$item" | jq -r '.reactions.url')
  if [ -z "$reactions_url" ] || [ "$reactions_url" == "null" ]; then return; fi

  gh api "$reactions_url" | jq -c '.[]' | while IFS= read -r reaction; do
    local content=$(echo "$reaction" | jq -r '.content')
    local created_at=$(echo "$reaction" | jq -r '.created_at' | cut -d'T' -f1)
    local points=0
    case "$content" in
      "+1") points=3 ;; "hooray" | "heart") points=2 ;; "rocket" | "laugh") points=1 ;;
      "confused") points=-1 ;; "-1") points=-2 ;; *) points=0 ;;
    esac
    echo "$created_at,$repo,$points"
  done
}
export -f process_single_reaction

# --- メインロジック ---

# オプションパース
show_summary_flag=false
fetch_all_users_flag=false
input_file=""

while getopts "saf:" opt; do
  case $opt in
    s) show_summary_flag=true ;;
    a) fetch_all_users_flag=true ;;
    f) input_file=$OPTARG ;;
    \?) echo "Invalid option: -$OPTARG" >&2; exit 1 ;;
  esac
done
shift $((OPTIND-1))

# -f オプションが指定された場合の処理
if [ -n "$input_file" ]; then
  if [ ! -f "$input_file" ]; then
    echo "Error: File not found: $input_file" >&2
    exit 1
  fi
  csv_data=$(cat "$input_file")
  show_summary_from_data "$csv_data"
  exit 0
fi

# データ収集
if [ "$#