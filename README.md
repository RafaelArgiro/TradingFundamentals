# TradingFundamentals

Small Streamlit apps for exploring trading fundamentals, starting with trade
expectancy. Everything runs locally in your browser and **requires no admin
rights**.

> New to any of this? [HOW_IT_WORKS.md](HOW_IT_WORKS.md) explains what virtual
> environments, packages, and Streamlit actually are, in plain language.

---

## 1. Prerequisites

| Requirement | Notes |
|---|---|
| **Python 3.12** | 3.11 or 3.13 will probably work, but 3.12 is what the pinned packages were tested against. |
| **Git** | Only needed to clone the repo. You can also download a ZIP. |
| **A browser** | Chrome, Edge, or Firefox. |

### Don't have Python? (still no admin needed)

Pick one:

- **python.org installer** — download Python 3.12 for Windows, run it, and
  **untick "Install for all users"** / tick **"Install just for me"**. It lands
  in `%LOCALAPPDATA%\Programs\Python` and never prompts for admin.
- **`uv`** — download `uv.exe`, put it in any folder, then `uv python install 3.12`.
  A single portable binary, no installer at all.

Verify it works:

```powershell
python --version
```

You should see `Python 3.12.x`.

---

## 2. First-time setup on a new machine

Run these **once**, from wherever you keep your projects.

### Step 1 — Get the code

```powershell
git clone https://github.com/RafaelArgiro/TradingFundamentals.git
cd TradingFundamentals
```

### Step 2 — Create the virtual environment

```powershell
python -m venv .venv
```

This creates a `.venv/` folder holding a private copy of Python. All packages
install *there*, not system-wide — which is exactly why no admin rights are
needed.

> **The `.venv/` folder is not in Git, and that is intentional.** It contains
> compiled binaries and absolute paths baked in at creation time, so it cannot
> be copied between machines. You always recreate it with this command.

### Step 3 — Install the dependencies

```powershell
& ".venv/Scripts/python.exe" -m pip install -r requirements.txt
```

This reads `requirements.txt` and installs the exact pinned versions. Expect it
to pull in ~45 packages (the five listed plus their dependencies) and take a
minute or two.

### Step 4 — Point VS Code at the environment

Open the folder in VS Code, then press `Ctrl+Shift+P` and run
**"Python: Select Interpreter"**. Choose the one whose path ends in
`.venv\Scripts\python.exe`.

This is only needed for editor features (IntelliSense, linting). The app runs
fine without it.

---

## 3. Running an app

From the repository root:

```powershell
& ".venv/Scripts/python.exe" -m streamlit run "01_Expectancy/app.py"
```

Your browser opens at <http://localhost:8501>. If it doesn't, `Ctrl+Click` the
URL printed in the terminal.

**To stop the app:** click in the terminal and press `Ctrl+C`.

### Why the command looks like that

- `& "..."` — PowerShell needs `&` to execute a quoted path. The quotes are
  required because this project's path may contain spaces.
- `-m streamlit` — invokes Streamlit *through* the venv's Python. This is more
  reliable than typing `streamlit` directly, which depends on `PATH` being set
  up correctly.

### Shorter alternative

If you activate the environment first, you can drop the long prefix for the
rest of that terminal session:

```powershell
.\.venv\Scripts\Activate.ps1
streamlit run 01_Expectancy/app.py
```

Your prompt will show `(.venv)` while it's active. Type `deactivate` to exit.

> If PowerShell blocks `Activate.ps1` with an execution-policy error, run
> `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` once.
> `-Scope CurrentUser` keeps it admin-free.

### On macOS or Linux

Identical, except the interpreter lives in `bin` instead of `Scripts`:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run 01_Expectancy/app.py
```

---

## 4. Daily use

Once set up, starting work is just:

```powershell
cd TradingFundamentals
& ".venv/Scripts/python.exe" -m streamlit run "01_Expectancy/app.py"
```

Edit the `.py` file and save — Streamlit detects the change and offers a
**Rerun** button in the browser. Click **"Always rerun"** once to make it
refresh automatically on every save.

---

## 5. Project layout

```
TradingFundamentals/
├── .venv/              # Local environment. Not in Git. Recreate per machine.
├── .streamlit/
│   └── config.toml     # Shared app settings (port, telemetry off).
├── 01_Expectancy/
│   └── app.py          # Setup smoke test / expectancy app.
├── requirements.txt    # Pinned dependencies — the portable recipe.
├── .gitignore
└── README.md
```

One virtual environment at the root serves every numbered subfolder. Future
projects (`02_...`, `03_...`) reuse it rather than each having their own.

---

## 6. Managing dependencies

### Adding a package

```powershell
& ".venv/Scripts/python.exe" -m pip install <package>
```

Then add it to `requirements.txt` with its version so other machines get it too:

```powershell
& ".venv/Scripts/python.exe" -m pip show <package>   # read the version
```

### Upgrading everything

```powershell
& ".venv/Scripts/python.exe" -m pip install --upgrade -r requirements.txt
```

Note this respects the `==` pins, so it won't actually move versions. To move
to newer releases, edit the version numbers in `requirements.txt` first, then
re-run the install and re-test the app.

### Capturing an exact snapshot

For a byte-identical rebuild including every transitive dependency:

```powershell
& ".venv/Scripts/python.exe" -m pip freeze > requirements.lock.txt
```

---

## 7. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `python : The term 'python' is not recognized` | Python isn't on `PATH`. Reinstall with "Add python.exe to PATH" ticked, or call it by full path. |
| `ModuleNotFoundError: No module named 'streamlit'` | You're running system Python, not the venv. Use the full `& ".venv/Scripts/python.exe"` prefix. |
| `Port 8501 is already in use` | An app is still running elsewhere. Close it, or add `--server.port 8502`. |
| `Activate.ps1 cannot be loaded` | Execution policy. See the note in section 3. |
| Browser never opens | Paste the `Local URL` from the terminal manually. |
| `pip install` times out or fails to resolve | Corporate proxy blocking PyPI. You may need `--proxy` or an internal index URL. |
| Terminal seems frozen after starting | Normal — the server is running and holds the terminal. `Ctrl+C` to stop. |

### Starting completely fresh

If the environment gets into a bad state, delete and rebuild it. Nothing of
value is lost:

```powershell
Remove-Item -Recurse -Force .venv
python -m venv .venv
& ".venv/Scripts/python.exe" -m pip install -r requirements.txt
```
