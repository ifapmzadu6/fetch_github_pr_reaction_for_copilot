#!/bin/bash

# --- 設定 ---
# 集計期間 (YYYY-MM-DD形式)
START_DATE="2025-05-01"
END_DATE="2025-06-26"

# Copilotのユーザー名
COPILOT_USER="github-actions[bot]"

# --- スクリプト本体 ---

show_summary=false

# -s オプションをパースする
while getopts "s" opt; do
  case $opt in
    s)
      show_summary=true
      ;;
    \?)
      echo "無効なオプションです: -$OPTARG" >&2
      exit 1
      ;;
  esac
done
shift $((OPTIND-1)) # パースしたオプションを引数リストから削除

if [ "$#" -eq 0 ]; then
  echo "エラー: 1つ以上のリポジトリを引数に指定してください (例: ./fetch_reactions.sh owner/repo)" >&2
  exit 1
fi

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

# --- データ収集 ---
# スクリプトの出力を変数に格納する
collected_data=$( \
for repo in "$@"; do
  pr_numbers=$(gh pr list -R "$repo" --search "created:$START_DATE..$END_DATE" --json number --jq '.[]?.number')

  for pr_number in $pr_numbers; do
    if [ -z "$pr_number" ]; then
      continue
    fi
    
    JQ_FILTER=".[] | select(.user.login == \"$COPILOT_USER\")"

    gh api "repos/$repo/issues/$pr_number/comments?per_page=100" | jq -c "$JQ_FILTER" | while IFS= read -r c; do process_reactions "$c" "$repo"; done
    gh api "repos/$repo/pulls/$pr_number/comments?per_page=100" | jq -c "$JQ_FILTER" | while IFS= read -r c; do process_reactions "$c" "$repo"; done
    gh api "repos/$repo/pulls/$pr_number/reviews?per_page=100" | jq -c "$JQ_FILTER" | while IFS= read -r r; do if echo "$r" | jq -e '.body != null and .body != ""' > /dev/null; then process_reactions "$r" "$repo"; fi; done
  done
done
)

# --- 結果の出力 ---

if [ "$show_summary" = true ]; then
  # サマリー表示モード
  if [ -z "$collected_data" ]; then
    echo "No applicable reactions found for the specified period and repositories."
    exit 0
  fi

  # awkで処理するためにヘッダーを付ける
  full_csv_data="date,repository,points\n$collected_data"

  echo "--- Daily Summary ---"
  echo "$full_csv_data" | awk -F, 'NR>1 {
      count[$1]++; 
      sum[$1]+=$3;
  } 
  END {
      print "Date          | Reactions | Total Points | Average Points";
      print "--------------|-----------|--------------|----------------";
      for (date in sum) {
          printf "%-13s | %-9d | %-12d | %.2f\n", date, count[date], sum[date], sum[date]/count[date];
      }
  }' | sort -k1

  echo ""
  echo "--- Weekly Summary ---"
  echo "$full_csv_data" | awk -F, 'NR>1 {
      cmd = "date -d " $1 " +%Y-%V"; 
      cmd | getline week; 
      close(cmd); 
      count[week]++; 
      sum[week]+=$3;
  } 
  END {
      print "Week          | Reactions | Total Points | Average Points";
      print "--------------|-----------|--------------|----------------";
      for (week in sum) {
          printf "%-13s | %-9d | %-12d | %.2f\n", week, count[week], sum[week], sum[week]/count[week];
      }
  }' | sort -k1

else
  # CSV出力モード (デフォルト)
  echo "date,repository,points"
  if [ -n "$collected_data" ]; then
    echo "$collected_data"
  fi
fi