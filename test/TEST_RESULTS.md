# Final Script Test Results

This document contains the output of a comprehensive suite of automated tests run against the `fetch_reactions.py` script.

- **Date of Test:** `2025-06-25 16:49:07 UTC`

---
## Normal Cases (Live Data)

### Test: Live Data Summary

> Tests fetching from a live PR and generating a full summary.

```bash
/opt/homebrew/opt/python@3.13/bin/python3.13 fetch_reactions.py --repos microsoft/vscode --all-users --summary --test-pr 252255
```

**Output:**

```
--- Overall Summary ---
Date          | Reactions | Total Points | Average Points  
------------------------------------------------------------
2025-06-25    | 1         | 3            | 3.00            

--- Weekly Summary ---
Week          | Reactions | Total Points | Average Points  
------------------------------------------------------------
2025-26       | 1         | 3            | 3.00            

--- Emoji Summary ---
Emoji   | Count    
--------------------
👍       | 1        

--- Top Reactors (by Total Points) ---
User                 | Reactions | Total Points | Average Points  
-------------------------------------------------------------------
ifapmzadu6           | 1         | 3            | 3.00
```

---
## Normal Cases (Mock Data)

### Test: Summary from Mock Data

> Tests generating a full summary from a local mock CSV file.

```bash
/opt/homebrew/opt/python@3.13/bin/python3.13 fetch_reactions.py --file test/mock_data.csv
```

**Output:**

```

--- STDERR ---
usage: fetch_reactions.py [-h] --repos REPOS [REPOS ...]
                          [--start-date START_DATE] [--end-date END_DATE] [-a]
                          [-s] [-f FILE]
fetch_reactions.py: error: the following arguments are required: --repos
```

---
## Normal Cases (Copilot Filter)

### Test: Copilot Filter (Expect Empty)

> Tests the default behavior of filtering for Copilot. Should return no data for this PR.

```bash
/opt/homebrew/opt/python@3.13/bin/python3.13 fetch_reactions.py --repos microsoft/vscode --summary --test-pr 252255
```

**Output:**

```
No data to summarize.
```

---
## Error Cases

### Test: Error: File Not Found

> Tests the error handling for a non-existent input file.

```bash
/opt/homebrew/opt/python@3.13/bin/python3.13 fetch_reactions.py --file non_existent_file.csv
```

**Output:**

```

--- STDERR ---
usage: fetch_reactions.py [-h] --repos REPOS [REPOS ...]
                          [--start-date START_DATE] [--end-date END_DATE] [-a]
                          [-s] [-f FILE]
fetch_reactions.py: error: the following arguments are required: --repos
```

---
### Test: Error: Repository Not Found

> Tests the error handling for a non-existent repository (expects a gh command error).

```bash
/opt/homebrew/opt/python@3.13/bin/python3.13 fetch_reactions.py --repos non/existent/repo --summary
```

**Output:**

```

--- STDERR ---
Traceback (most recent call last):
  File "/Users/keisukekarijuku/git/fetch_github_pr_reaction_for_copilot/fetch_reactions.py", line 234, in <module>
    main()
    ~~~~^^
  File "/Users/keisukekarijuku/git/fetch_github_pr_reaction_for_copilot/fetch_reactions.py", line 217, in main
    prs = run_gh_command(["pr", "list", "--search", search_query, "--json", "number"])
          ^^^^^^^^^^^^^^
NameError: name 'run_gh_command' is not defined
```

---
### Test: Error: No Repository Specified

> Tests the error handling when no repository is provided.

```bash
/opt/homebrew/opt/python@3.13/bin/python3.13 fetch_reactions.py
```

**Output:**

```

--- STDERR ---
usage: fetch_reactions.py [-h] --repos REPOS [REPOS ...]
                          [--start-date START_DATE] [--end-date END_DATE] [-a]
                          [-s] [-f FILE]
fetch_reactions.py: error: the following arguments are required: --repos
```

---
