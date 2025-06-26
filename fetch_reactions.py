

import argparse
import subprocess
import json
import sys
from datetime import datetime
from collections import defaultdict

# --- 設定 ---
COPILOT_USER = "github-actions[bot]"

# --- ポイント換算 ---
POINTS_MAP = {
    "THUMBS_UP": 3,      # 👍
    "HOORAY": 2,         # 🎉
    "HEART": 2,          # ❤️
    "ROCKET": 1,         # 🚀
    "LAUGH": 1,          # 😄
    "CONFUSED": -1,      # 🤔
    "THUMBS_DOWN": -2,   # 👎
}

def run_gh_command(command_args):
    """ghコマンドを実行し、結果をJSONとしてパースして返す"""
    cmd = ["gh"] + command_args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            encoding='utf-8'
        )
        return json.loads(result.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        # print(f"gh command Error: {e}", file=sys.stderr)
        # if hasattr(e, 'stderr'):
        #     print(f"Stderr: {e.stderr}", file=sys.stderr)
        return None

# --- GraphQL クエリ ---
# このクエリは、指定されたリポジリとPR番号について、
# 関連するコメント、レビュー、リアクションを一度に取得します。
GRAPHQL_QUERY = """
query($owner: String!, $repo: String!, $prNumber: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $prNumber) {
      comments(first: 30) {
        nodes {
          author { login }
          reactions(first: 30) { nodes { content createdAt user { login } } }
        }
      }
      reviews(first: 30) {
        nodes {
          author { login }
          body
          reactions(first: 30) { nodes { content createdAt user { login } } }
          comments(first: 30) {
            nodes {
              author { login }
              reactions(first: 30) { nodes { content createdAt user { login } } }
            }
          }
        }
      }
    }
  }
}
"""

def run_gh_graphql(query, variables):
    """ghコマンド経由でGraphQLクエリを実行する"""
    cmd = [
        "gh", "api", "graphql", 
        "-f", f"query={query}",
        "-F", f"owner={variables['owner']}",
        "-F", f"repo={variables['repo']}",
        "-F", f"prNumber={variables['prNumber']}"
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True, 
            text=True, 
            check=True,
            encoding='utf-8'
        )
        return json.loads(result.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        # print(f"GraphQL Error: {e}", file=sys.stderr)
        # print(f"Stderr: {e.stderr}", file=sys.stderr)
        return None

def parse_reactions(reaction_nodes):
    """リアクションのノードをパースしてCSV行のリストを生成する"""
    lines = []
    for reaction in reaction_nodes:
        user = reaction.get("user", {}).get("login", "unknown-user")
        # GraphQLのリアクション内容はEnum形式 (e.g., THUMBS_UP)
        content_enum = reaction.get("content")
        points = POINTS_MAP.get(content_enum, 0)
        created_at = reaction.get("createdAt", "").split("T")[0]
        lines.append(f"{created_at},{user},{points}")
    return lines

def fetch_data_for_pr_graphql(repo_full, pr_number, all_users):
    """GraphQLを使って単一のPRからデータを収集する"""
    owner, repo_name = repo_full.split('/')
    variables = {"owner": owner, "repo": repo_name, "prNumber": pr_number}
    
    data = run_gh_graphql(GRAPHQL_QUERY, variables)
    if not data or "data" not in data or not data["data"].get("repository", {}).get("pullRequest"):
        return []

    pr_data = data["data"]["repository"]["pullRequest"]
    all_reactions = []

    # 1. Issueコメントのリアクション
    for comment in pr_data.get("comments", {}).get("nodes", []):
        if all_users or comment.get("author", {}).get("login") == COPILOT_USER:
            all_reactions.extend(parse_reactions(comment.get("reactions", {}).get("nodes", [])))

    # 2. レビューとレビューコメントのリアクション
    for review in pr_data.get("reviews", {}).get("nodes", []):
        # レビュー要約へのリアクション
        if all_users or review.get("author", {}).get("login") == COPILOT_USER:
            if review.get("body"): # 本文があるもののみ
                all_reactions.extend(parse_reactions(review.get("reactions", {}).get("nodes", [])))
        
        # レビューコメントへのリアクション
        for review_comment in review.get("comments", {}).get("nodes", []):
            if all_users or review_comment.get("author", {}).get("login") == COPILOT_USER:
                all_reactions.extend(parse_reactions(review_comment.get("reactions", {}).get("nodes", [])))

    # 最終的なCSV行の前にリポジトリ名を追加
    return [f"{line.split(',')[0]},{repo_full},{line.split(',', 1)[1]}" for line in all_reactions]

def show_summary(csv_data):
    lines = csv_data.strip().split('\n')
    if len(lines) <= 1:
        print("No data to summarize.")
        return

    daily_data = defaultdict(lambda: {"count": 0, "sum": 0})
    weekly_data = defaultdict(lambda: {"count": 0, "sum": 0})
    user_data = defaultdict(lambda: {"count": 0, "sum": 0, "reactions": defaultdict(int)})
    emoji_data = defaultdict(int)

    # ポイントから絵文字への逆引きマップを作成
    # 同じポイントの絵文字は代表的なものを一つ選ぶ
    POINTS_TO_EMOJI = {
        3: "👍", 2: "❤️", 1: "🚀", -1: "🤔", -2: "👎", 0: "👀"
    }

    for line in lines[1:]:
        try:
            date_str, _, user, points_str = line.split(',')
            points = int(points_str)
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        except (ValueError, IndexError):
            continue
        
        daily_data[date_str]["count"] += 1
        daily_data[date_str]["sum"] += points
        
        week_str = dt.strftime("%Y-%V")
        weekly_data[week_str]["count"] += 1
        weekly_data[week_str]["sum"] += points
        
        user_data[user]["count"] += 1
        user_data[user]["sum"] += points
        
        emoji = POINTS_TO_EMOJI.get(points, "❓")
        emoji_data[emoji] += 1
        user_data[user]["reactions"][emoji] += 1

    print("--- Overall Summary ---")
    print(f"{'Date':<13} | {'Reactions':<9} | {'Total Points':<12} | {'Average Points':<16}")
    print("-" * 60)
    for date, data in sorted(daily_data.items()):
        avg = data["sum"] / data["count"]
        print(f"{date:<13} | {data['count']:<9} | {data['sum']:<12} | {avg:<16.2f}")

    print("\n--- Weekly Summary ---")
    print(f"{'Week':<13} | {'Reactions':<9} | {'Total Points':<12} | {'Average Points':<16}")
    print("-" * 60)
    for week, data in sorted(weekly_data.items()):
        avg = data["sum"] / data["count"]
        print(f"{week:<13} | {data['count']:<9} | {data['sum']:<12} | {avg:<16.2f}")

    print("\n--- Emoji Summary ---")
    print(f"{'Emoji':<7} | {'Count':<9}")
    print("-" * 20)
    for emoji, count in sorted(emoji_data.items(), key=lambda item: item[1], reverse=True):
        print(f"{emoji:<7} | {count:<9}")

    print("\n--- Top Reactors (by Total Points) ---")
    print(f"{'User':<20} | {'Reactions':<9} | {'Total Points':<12} | {'Average Points':<16}")
    print("-" * 67)
    for user, data in sorted(user_data.items(), key=lambda item: item[1]['sum'], reverse=True)[:10]: # 上位10名
        avg = data["sum"] / data["count"]
        print(f"{user:<20} | {data['count']:<9} | {data['sum']:<12} | {avg:<16.2f}")

def main():
    parser = argparse.ArgumentParser(description="Fetch GitHub PR reactions using GraphQL.")
    parser.add_argument("--repos", nargs='+', required=True, help="List of repositories (e.g., owner/repo)")
    parser.add_argument("--start-date", default="2025-05-01")
    parser.add_argument("--end-date", default="2025-06-26")
    parser.add_argument("-a", "--all-users", action="store_true", help="Fetch reactions for all users.")
    parser.add_argument("-s", "--summary", action="store_true", help="Show summary instead of CSV.")
    parser.add_argument("-f", "--file", help="Generate summary from an existing CSV file.")
    parser.add_argument("--test-pr", type=int, help=argparse.SUPPRESS)

    args = parser.parse_args()

    if args.file:
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                csv_data = f.read()
            show_summary(csv_data)
        except FileNotFoundError:
            print(f"Error: File not found: {args.file}", file=sys.stderr)
            sys.exit(1)
        return

    all_results = []
    for repo in args.repos:
        if args.test_pr:
            pr_numbers = [args.test_pr]
        else:
            # REST APIでPR番号を検索 (ここはGraphQLよりRESTの方がシンプル)
            search_query = f'repo:{repo} is:pr created:{args.start_date}..{args.end_date}'
            prs = run_gh_command(["pr", "list", "--search", search_query, "--json", "number"])
            pr_numbers = [pr["number"] for pr in prs] if prs else []

        for pr_number in pr_numbers:
            all_results.extend(fetch_data_for_pr_graphql(repo, pr_number, args.all_users))

    header = "date,repository,user,points"
    # 重複を除去 (複数のコメントタイプで同じリアクションを取得する可能性があるため)
    unique_results = sorted(list(set(all_results)))
    csv_output = "\n".join([header] + unique_results)

    if args.summary:
        show_summary(csv_output)
    else:
        print(csv_output)

if __name__ == "__main__":
    main()
