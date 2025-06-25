import argparse
import subprocess
import json
import sys
from datetime import datetime

# --- 設定 ---
COPILOT_USER = "github-actions[bot]"

# --- ポイント換算 ---
POINTS_MAP = {
    "+1": 3,
    "hooray": 2,
    "heart": 2,
    "rocket": 1,
    "laugh": 1,
    "confused": -1,
    "-1": -2,
}

def run_gh_command(command):
    """ghコマンドを実行し、結果をJSONとしてパースする"""
    try:
        result = subprocess.run(
            ["gh"] + command, 
            capture_output=True, 
            text=True, 
            check=True
        )
        return json.loads(result.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        # print(f"Error running command 'gh {' '.join(command)}': {e}", file=sys.stderr)
        return None

def get_reactions(api_url):
    """リアクションAPIのURLからリアクションデータを取得する"""
    if not api_url:
        return []
    # gh apiの引数はURLのパス部分のみ
    path = api_url.replace("https://api.github.com/", "")
    reactions_data = run_gh_command(["api", path])
    return reactions_data if reactions_data else []

def process_item(item, repo, all_users):
    """単一のコメントやレビューからリアクションを処理する"""
    if not all_users and item.get("user", {}).get("login") != COPILOT_USER:
        return []

    # レビューの場合、本文がないものはスキップ
    if "/reviews/" in item.get("url", "") and not item.get("body"): 
        return []

    reactions = get_reactions(item.get("reactions", {}).get("url"))
    output = []
    for reaction in reactions:
        content = reaction.get("content")
        points = POINTS_MAP.get(content, 0)
        created_at = reaction.get("created_at", "").split("T")[0]
        output.append(f"{created_at},{repo},{points}")
    return output

def fetch_data_for_pr(repo, pr_number, all_users):
    """単一のPRからすべてのコメントとリアクションを収集する"""
    endpoints = [
        f"repos/{repo}/issues/{pr_number}/comments",
        f"repos/{repo}/pulls/{pr_number}/comments",
        f"repos/{repo}/pulls/{pr_number}/reviews",
    ]
    all_reactions = []
    for endpoint in endpoints:
        items = run_gh_command(["api", f"{endpoint}?per_page=100"])
        if not items:
            continue
        for item in items:
            all_reactions.extend(process_item(item, repo, all_users))
    return all_reactions

def show_summary(csv_data):
    """CSVデータからサマリーを計算して表示する"""
    lines = csv_data.strip().split('\n')
    if len(lines) <= 1:
        print("No data to summarize.")
        return

    daily_data = {}
    weekly_data = {}

    for line in lines[1:]:
        date_str, _, points_str = line.split(',')
        points = int(points_str)
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        
        # 日別集計
        if date_str not in daily_data:
            daily_data[date_str] = {"count": 0, "sum": 0}
        daily_data[date_str]["count"] += 1
        daily_data[date_str]["sum"] += points

        # 週別集計
        week_str = dt.strftime("%Y-%V")
        if week_str not in weekly_data:
            weekly_data[week_str] = {"count": 0, "sum": 0}
        weekly_data[week_str]["count"] += 1
        weekly_data[week_str]["sum"] += points

    print("--- Daily Summary ---")
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

def main():
    parser = argparse.ArgumentParser(description="Fetch GitHub PR reactions.")
    parser.add_argument("--repos", nargs='+', help="List of repositories (e.g., owner/repo)")
    parser.add_argument("--start-date", default="2025-05-01")
    parser.add_argument("--end-date", default="2025-06-26")
    parser.add_argument("-a", "--all-users", action="store_true", help="Fetch reactions for all users.")
    parser.add_argument("-s", "--summary", action="store_true", help="Show summary instead of CSV.")
    parser.add_argument("-f", "--file", help="Generate summary from an existing CSV file.")
    # テスト用の非表示オプション
    parser.add_argument("--test-pr", help=argparse.SUPPRESS)

    args = parser.parse_args()

    if args.file:
        try:
            with open(args.file, 'r') as f:
                csv_data = f.read()
            show_summary(csv_data)
        except FileNotFoundError:
            print(f"Error: File not found: {args.file}", file=sys.stderr)
            sys.exit(1)
        return

    if not args.repos:
        parser.error("the following arguments are required: --repos")
        return

    all_results = []
    for repo in args.repos:
        if args.test_pr:
            pr_numbers = [args.test_pr]
        else:
            search_query = f'repo:{repo} is:pr created:{args.start_date}..{args.end_date}'
            prs = run_gh_command(["pr", "list", "--search", search_query, "--json", "number"])
            pr_numbers = [pr["number"] for pr in prs] if prs else []

        for pr_number in pr_numbers:
            all_results.extend(fetch_data_for_pr(repo, pr_number, args.all_users))

    header = "date,repository,points"
    csv_output = "\n".join([header] + all_results)

    if args.summary:
        show_summary(csv_output)
    else:
        print(csv_output)

if __name__ == "__main__":
    main()
