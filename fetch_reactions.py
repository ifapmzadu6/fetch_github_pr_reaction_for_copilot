

import argparse
import subprocess
import json
import sys
from datetime import datetime
from collections import defaultdict
import logging
from typing import Dict, List, Optional, Tuple, Any

# --- デフォルト設定 ---
DEFAULT_COPILOT_USER = "github-copilot[bot]"
DEFAULT_POINTS_MAP = {
    "THUMBS_UP": 3,      # 👍
    "HOORAY": 2,         # 🎉
    "HEART": 2,          # ❤️
    "ROCKET": 1,         # 🚀
    "LAUGH": 1,          # 😄
    "CONFUSED": -1,      # 🤔
    "THUMBS_DOWN": -2,   # 👎
}

# ログ設定
logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')

class Config:
    """設定管理クラス"""
    def __init__(self, copilot_user: Optional[str] = None, points_map: Optional[Dict[str, int]] = None) -> None:
        self.copilot_user: str = copilot_user or DEFAULT_COPILOT_USER
        self.points_map: Dict[str, int] = points_map or DEFAULT_POINTS_MAP.copy()

def run_gh_command(command_args: List[str]) -> Optional[Any]:
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
    except subprocess.CalledProcessError as e:
        logging.error(f"gh command failed: {' '.join(cmd)}")
        logging.error(f"Return code: {e.returncode}")
        if e.stderr:
            logging.error(f"Error output: {e.stderr}")
        return None
    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse JSON response from gh command")
        logging.error(f"Command: {' '.join(cmd)}")
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

def run_gh_graphql(query: str, variables: Dict[str, Any]) -> Optional[Any]:
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
    except subprocess.CalledProcessError as e:
        logging.error(f"GraphQL command failed: {' '.join(cmd)}")
        logging.error(f"Return code: {e.returncode}")
        if e.stderr:
            logging.error(f"Error output: {e.stderr}")
        return None
    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse GraphQL JSON response")
        logging.error(f"Variables: {variables}")
        return None

def parse_reactions(reaction_nodes: List[Dict[str, Any]], config: Config) -> List[str]:
    """リアクションのノードをパースしてCSV行のリストを生成する"""
    lines = []
    for reaction in reaction_nodes:
        user = reaction.get("user", {}).get("login", "unknown-user")
        # GraphQLのリアクション内容はEnum形式 (e.g., THUMBS_UP)
        content_enum = reaction.get("content")
        points = config.points_map.get(content_enum, 0)
        created_at = reaction.get("createdAt", "").split("T")[0]
        lines.append(f"{created_at},{user},{points}")
    return lines

def fetch_data_for_pr_graphql(repo_full: str, pr_number: int, all_users: bool, config: Config) -> Tuple[List[str], bool]:
    """GraphQLを使って単一のPRからデータを収集する"""
    owner, repo_name = repo_full.split('/')
    variables = {"owner": owner, "repo": repo_name, "prNumber": pr_number}
    
    data = run_gh_graphql(GRAPHQL_QUERY, variables)
    if not data or "data" not in data or not data["data"].get("repository", {}).get("pullRequest"):
        return [], False  # コメント不在も返す

    pr_data = data["data"]["repository"]["pullRequest"]
    all_reactions = []
    has_copilot_comments = False

    # 1. Issueコメントのリアクション
    for comment in pr_data.get("comments", {}).get("nodes", []):
        if comment.get("author", {}).get("login") == config.copilot_user:
            has_copilot_comments = True
        if all_users or comment.get("author", {}).get("login") == config.copilot_user:
            all_reactions.extend(parse_reactions(comment.get("reactions", {}).get("nodes", []), config))

    # 2. レビューとレビューコメントのリアクション
    for review in pr_data.get("reviews", {}).get("nodes", []):
        # レビュー要約へのリアクション
        if review.get("author", {}).get("login") == config.copilot_user:
            has_copilot_comments = True
        if all_users or review.get("author", {}).get("login") == config.copilot_user:
            if review.get("body"): # 本文があるもののみ
                all_reactions.extend(parse_reactions(review.get("reactions", {}).get("nodes", []), config))
        
        # レビューコメントへのリアクション
        for review_comment in review.get("comments", {}).get("nodes", []):
            if review_comment.get("author", {}).get("login") == config.copilot_user:
                has_copilot_comments = True
            if all_users or review_comment.get("author", {}).get("login") == config.copilot_user:
                all_reactions.extend(parse_reactions(review_comment.get("reactions", {}).get("nodes", []), config))

    # 最終的なCSV行の前にリポジトリ名を追加
    reactions_data = [f"{line.split(',')[0]},{repo_full},{line.split(',', 1)[1]}" for line in all_reactions]
    return reactions_data, has_copilot_comments

def show_summary(csv_data: str, no_comment_prs: Optional[List[int]] = None) -> None:
    lines = csv_data.strip().split('\n')
    if len(lines) <= 1:
        print("No data to summarize.")
        return

    daily_data = defaultdict(lambda: {"count": 0, "sum": 0})
    weekly_data = defaultdict(lambda: {"count": 0, "sum": 0})
    user_data = defaultdict(lambda: {"count": 0, "sum": 0, "reactions": defaultdict(int)})
    emoji_data = defaultdict(int)
    
    # レビュー精度指標用
    low_quality_reactions = 0  # 混乱や否定的なリアクション
    total_reactions = 0

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
        
        total_reactions += 1
        if points < 0:  # 否定的なリアクション
            low_quality_reactions += 1
        
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

    print("\n--- Per-User Summary ---")
    print(f"{'User':<20} | {'Reactions':<9} | {'Total Points':<12} | {'Average Points':<16}")
    print("-" * 67)
    for user, data in sorted(user_data.items(), key=lambda item: item[1]['sum'], reverse=True):
        avg = data["sum"] / data["count"]
        print(f"{user:<20} | {data['count']:<9} | {data['sum']:<12} | {avg:<16.2f}")

    # レビュー精度指標
    print("\n--- Review Quality Metrics ---")
    if total_reactions > 0:
        negative_rate = (low_quality_reactions / total_reactions) * 100
        print(f"Total Reactions: {total_reactions}")
        print(f"Negative Reactions: {low_quality_reactions} ({negative_rate:.1f}%)")
        if negative_rate > 20:
            print("⚠️ High negative reaction rate - Review quality may be low")
    
    # コメント不在PR情報
    if no_comment_prs:
        print(f"\n--- PRs without Copilot Comments ---")
        print(f"Total PRs without comments: {len(no_comment_prs)}")
        if no_comment_prs:
            print("PR Numbers:", ", ".join(map(str, no_comment_prs[:10])))
            if len(no_comment_prs) > 10:
                print(f"... and {len(no_comment_prs) - 10} more")

def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch GitHub PR reactions using GraphQL.")
    parser.add_argument("--repos", nargs='+', required=True, help="List of repositories (e.g., owner/repo)")
    parser.add_argument("--start-date", default="2025-05-01")
    parser.add_argument("--end-date", default="2025-06-26")
    parser.add_argument("-a", "--all-users", action="store_true", help="Fetch reactions for all users.")
    parser.add_argument("-s", "--summary", action="store_true", help="Show summary instead of CSV.")
    parser.add_argument("-f", "--file", help="Generate summary from an existing CSV file.")
    parser.add_argument("--copilot-user", default=DEFAULT_COPILOT_USER, 
                       help=f"GitHub username for Copilot (default: {DEFAULT_COPILOT_USER})")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    parser.add_argument("--test-pr", type=int, help=argparse.SUPPRESS)

    args = parser.parse_args()
    
    # ログレベル設定
    if args.verbose:
        logging.getLogger().setLevel(logging.INFO)
    
    # 設定オブジェクト作成
    config = Config(copilot_user=args.copilot_user)

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
    no_comment_prs = []
    
    for repo in args.repos:
        if args.test_pr:
            pr_numbers = [args.test_pr]
        else:
            # REST APIでPR番号を検索 (ここはGraphQLよりRESTの方がシンプル)
            search_query = f'repo:{repo} is:pr created:{args.start_date}..{args.end_date}'
            prs = run_gh_command(["pr", "list", "--search", search_query, "--json", "number"])
            pr_numbers = [pr["number"] for pr in prs] if prs else []

        if args.verbose:
            print(f"Processing {len(pr_numbers)} PRs from {repo}...", file=sys.stderr)
        
        for i, pr_number in enumerate(pr_numbers, 1):
            if args.verbose:
                print(f"  Processing PR #{pr_number} ({i}/{len(pr_numbers)})", file=sys.stderr)
            
            reactions_data, has_copilot_comments = fetch_data_for_pr_graphql(repo, pr_number, args.all_users, config)
            all_results.extend(reactions_data)
            
            # GitHub Copilotのコメントがない場合を記録
            if not has_copilot_comments and not args.all_users:
                no_comment_prs.append(pr_number)

    header = "date,repository,user,points"
    # 重複を除去 (複数のコメントタイプで同じリアクションを取得する可能性があるため)
    # O(n log n)で効率的に重複除去
    seen = set()
    unique_results = []
    for result in all_results:
        if result not in seen:
            seen.add(result)
            unique_results.append(result)
    unique_results.sort()
    csv_output = "\n".join([header] + unique_results)

    if args.summary:
        show_summary(csv_output, no_comment_prs)
    else:
        print(csv_output)

if __name__ == "__main__":
    main()
