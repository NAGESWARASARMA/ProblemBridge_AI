# ProblemBridge AI — local prototype

## Features
- Home page has exactly the main actions: **Problem Deployer**, **Problem Solver**, plus **Solved Problems**.
- Deployer chooses Free or Paid, then enters problem title, statement, requirements, category, deadline and (for Paid) a budget amount.
- Solver has separate Free and Paid project pages, category zones, search and Most Viewed/Newest sorting.
- Problem detail pages show requirements and allow signed-in users to submit a solution description and project files.
- Poster can review and accept a submitted solution. Accepted projects appear in Solved Problems with poster and solver attribution.
- Basic per-project chat is available to the poster and people who submitted solutions.
- Login, registration and dashboard.
- Database uses SQLite. A few DEMO-labelled example projects are inserted the first time to show the interface.

## Windows setup
1. Extract the ZIP.
2. Open the extracted folder in VS Code.
3. Open Terminal > New Terminal and run:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
py app.py
```

If PowerShell blocks activation, run `py -m pip install -r requirements.txt` and then `py app.py`.
4. Open http://127.0.0.1:5000

## Demo login
- Username: `demo_poster`
- Password: `demo-password-123`
- Username: `demo_solver`
- Password: `demo-password-123`

Create your own account for normal testing. Demo records are clearly marked as examples.

## Important
- This is a local prototype, not a production marketplace.
- **No actual payments or money transfers are implemented.** Paid posts display a poster-set budget. Chat is for discussion only; do not transfer money based on this prototype.
- For a public launch, add CSRF protection, secure secret configuration, HTTPS, file size limits, stronger file scanning, moderation, backups, audit logs, privacy policy, and reviewed payment/IP agreements.
- File uploads are restricted by extension and access-checked, but production needs stronger security controls.
- Paid/free choice belongs to the **Problem Deployer**. Solvers cannot change it.
- Free does not automatically mean the poster owns all intellectual property. Agree on license and ownership terms separately.
