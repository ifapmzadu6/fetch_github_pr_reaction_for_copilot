#!/bin/bash

# --- 設定 ---
START_DATE="2025-05-01"
END_DATE="2025-06-26"
COPILOT_USER="github-actions[bot]"

# --- オプションパース ---
show_summary=false
fetch_all_users=false
while getopts "sa" opt; do
  case $opt in
    s) show_summary=true ;; 
    a) fetch_all_users=true ;; 
    \?) echo "Invalid option: -$OPTARG" >&2; exit 1 ;;
  esac
done
shift $((OPTIND-1))

if [ "$#" -eq 0 ]; then
  echo "Error: Please specify at least one repository." >&2
  exit 1
fi

# --- 関数定義 ---
process_reactions() {
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
export -f process_reactions

# --- データ収集 ---
collected_data=(
  for repo in "$@"; do
    # PR番号を期間で検索
    gh pr list -R "$repo" --search "created:$START_DATE..$END_DATE" --json number --jq '.[] | .number' | while read -r pr_number; do
      if [ -z "$pr_number" ]; then continue; fi
      
      if [ "$fetch_all_users" = true ]; then
        JQ_FILTER=".[]"
      else
        JQ_FILTER=".[] | select(.user.login == \"$COPILOT_USER\")"
      fi

      gh api "repos/$repo/issues/$pr_number/comments?per_page=100" | jq -c "$JQ_FILTER" | while IFS= read -r c; do process_reactions "$c" "$repo"; done
      gh api "repos/$repo/pulls/$pr_number/comments?per_page=100" | jq -c "$JQ_FILTER" | while IFS= read -r c; do process_reactions "$c" "$repo"; done
      gh api "repos/$repo/pulls/$pr_number/reviews?per_page=100" | jq -c "$JQ_FILTER" | while IFS= read -r r; do if echo "$r" | jq -e '.body != null and .body != ""' > /dev/null; then process_reactions "$r" "$repo"; fi; done
    done
  done
)

# --- 結果の出力 ---
if [ "$show_summary" = true ]; then
  if [ -z "$collected_data" ]; then
    echo "No applicable reactions found."
    exit 0
  fi
  
  echo "--- Daily Summary ---"
  daily_summary=$(echo "$collected_data" | awk -F, '{count[$1]++; sum[$1]+=$3} END {for (d in sum) {printf "%-13s | %-9d | %-12d | %.2f\n", d, count[d], sum[d], sum[d]/count[d]}}' | sort -k1)
  echo -e "Date          | Reactions | Total Points | Average Points\n--------------|-----------|--------------|----------------\n$daily_summary"

  echo ""
  echo "--- Weekly Summary ---"
  weekly_summary=$(echo "$collected_data" | awk -F, '{cmd="date -d "$1" +%Y-%V"; cmd|getline w; close(cmd); count[w]++; sum[w]+=$3} END {for (w in sum) {printf "%-13s | %-9d | %-12d | %.2f\n", w, count[w], sum[w], sum[w]/count[w]}}' | sort -k1)
  echo -e "Week          | Reactions | Total Points | Average Points\n--------------|-----------|--------------|----------------\n$weekly_summary"
else
  echo "date,repository,points"
  echo "$collected_data"
fi
