import subprocess
import sys
from datetime import datetime

# --- Test Configuration ---
REPO = "microsoft/vscode"
TEST_PR = "252255"
MOCK_DATA_FILE = "test/mock_data.csv"
REAL_DATA_FILE = "test/real_data.csv"
REPORT_FILE = "test/TEST_RESULTS.md"
PYTHON_CMD = sys.executable

def run_test(title, command, description):
    report_content = f"### Test: {title}\n\n"
    report_content += f"> {description}\n\n"
    report_content += f"```bash\n{command}\n```\n\n"
    report_content += "**Output:**\n\n"
    report_content += "```\n"
    
    try:
        result = subprocess.run(
            command, 
            shell=True,
            capture_output=True, 
            text=True, 
            encoding='utf-8'
        )
        # 標準出力と標準エラーを両方記録
        report_content += result.stdout.strip()
        if result.stderr:
            report_content += "\n--- STDERR ---\n"
            report_content += result.stderr.strip()
    except Exception as e:
        report_content += f"An error occurred: {e}"

    report_content += "\n```\n\n---\n"
    return report_content

def main():
    with open(REPORT_FILE, 'w', encoding='utf-8') as f:
        f.write(f"# Final Script Test Results\n\n")
        f.write("This document contains the output of a comprehensive suite of automated tests run against the `fetch_reactions.py` script.\n\n")
        f.write(f"- **Date of Test:** `{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}`\n\n---\n")

        # --- Normal Cases (Live Data) ---
        f.write("## Normal Cases (Live Data)\n\n")
        cmd1 = f'{PYTHON_CMD} fetch_reactions.py --repos {REPO} --all-users --summary --test-pr {TEST_PR}'
        f.write(run_test("Live Data Summary", cmd1, "Tests fetching from a live PR and generating a full summary."))

        # --- Normal Cases (Mock Data) ---
        f.write("## Normal Cases (Mock Data)\n\n")
        cmd2 = f'{PYTHON_CMD} fetch_reactions.py --file {MOCK_DATA_FILE}'
        f.write(run_test("Summary from Mock Data", cmd2, "Tests generating a full summary from a local mock CSV file."))

        # --- Normal Cases (Copilot Filter) ---
        f.write("## Normal Cases (Copilot Filter)\n\n")
        cmd3 = f'{PYTHON_CMD} fetch_reactions.py --repos {REPO} --summary --test-pr {TEST_PR}'
        f.write(run_test("Copilot Filter (Expect Empty)", cmd3, "Tests the default behavior of filtering for Copilot. Should return no data for this PR."))

        # --- Error Cases ---
        f.write("## Error Cases\n\n")
        cmd4 = f'{PYTHON_CMD} fetch_reactions.py --file non_existent_file.csv'
        f.write(run_test("Error: File Not Found", cmd4, "Tests the error handling for a non-existent input file."))

        cmd5 = f'{PYTHON_CMD} fetch_reactions.py --repos non/existent/repo --summary'
        f.write(run_test("Error: Repository Not Found", cmd5, "Tests the error handling for a non-existent repository (expects a gh command error)."))
        
        cmd6 = f'{PYTHON_CMD} fetch_reactions.py'
        f.write(run_test("Error: No Repository Specified", cmd6, "Tests the error handling when no repository is provided."))

    print(f"Test report generated: {REPORT_FILE}")

if __name__ == "__main__":
    main()
