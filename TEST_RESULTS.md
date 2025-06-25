# Script Test Results

This document contains the output of a series of automated tests run against the `fetch_reactions.py` script to verify its functionality with live data.

- **Repository:** `microsoft/vscode`
- **Pull Request:** `#204506`
- **Date of Test:** `2025-06-25 16:19:13 UTC`

---
### Test: CSV Output (All Users)

```bash
/opt/homebrew/opt/python@3.13/bin/python3.13 fetch_reactions.py --repos microsoft/vscode --all-users --test-pr 204506 > test_results.csv && cat test_results.csv
```

**Output:**

```
date,repository,user,points
2024-02-06,microsoft/vscode,josephgarnier,3
2024-02-09,microsoft/vscode,spartanatreyu,3
2024-02-21,microsoft/vscode,senyai,3
2024-02-08,microsoft/vscode,josephgarnier,2
2024-02-09,microsoft/vscode,spartanatreyu,2

```

---
### Test: Summary Output (All Users)

```bash
/opt/homebrew/opt/python@3.13/bin/python3.13 fetch_reactions.py --repos microsoft/vscode --all-users --summary --test-pr 204506
```

**Output:**

```
--- Daily Summary ---
Date          | Reactions | Total Points | Average Points  
------------------------------------------------------------
2024-02-06    | 1         | 3            | 3.00            
2024-02-08    | 1         | 2            | 2.00            
2024-02-09    | 2         | 5            | 2.50            
2024-02-21    | 1         | 3            | 3.00            

--- Weekly Summary ---
Week          | Reactions | Total Points | Average Points  
------------------------------------------------------------
2024-06       | 4         | 10           | 2.50            
2024-08       | 1         | 3            | 3.00            

--- Per-User Summary ---
User                 | Reactions | Total Points | Average Points  
-------------------------------------------------------------------
josephgarnier        | 2         | 5            | 2.50            
spartanatreyu        | 2         | 5            | 2.50            
senyai               | 1         | 3            | 3.00            

```

---
### Test: Summary from File

```bash
/opt/homebrew/opt/python@3.13/bin/python3.13 fetch_reactions.py --file test_results.csv
```

**Output:**

```
--- Daily Summary ---
Date          | Reactions | Total Points | Average Points  
------------------------------------------------------------
2024-02-06    | 1         | 3            | 3.00            
2024-02-08    | 1         | 2            | 2.00            
2024-02-09    | 2         | 5            | 2.50            
2024-02-21    | 1         | 3            | 3.00            

--- Weekly Summary ---
Week          | Reactions | Total Points | Average Points  
------------------------------------------------------------
2024-06       | 4         | 10           | 2.50            
2024-08       | 1         | 3            | 3.00            

--- Per-User Summary ---
User                 | Reactions | Total Points | Average Points  
-------------------------------------------------------------------
josephgarnier        | 2         | 5            | 2.50            
spartanatreyu        | 2         | 5            | 2.50            
senyai               | 1         | 3            | 3.00            

```

---
### Test: CSV Output (Copilot Only - Expect Empty)

```bash
/opt/homebrew/opt/python@3.13/bin/python3.13 fetch_reactions.py --repos microsoft/vscode --test-pr 204506
```

**Output:**

```
date,repository,user,points

```

---
### Test: Summary Output (Copilot Only - Expect Empty)

```bash
/opt/homebrew/opt/python@3.13/bin/python3.13 fetch_reactions.py --repos microsoft/vscode --summary --test-pr 204506
```

**Output:**

```
No data to summarize.

```

---
