# Cricket King — Demo Coins only

A small Flask + SQLite cricket prediction demo. It uses fictional fixtures and virtual coins only.
There are no deposits, withdrawals, payment integrations, cash prizes, or real-money betting.

## Run locally
1. Install Python 3.10+.
2. Open a terminal in this folder.
3. Create and activate a virtual environment (recommended).
4. Run: `pip install -r requirements.txt`
5. Run: `python app.py`
6. Visit: http://127.0.0.1:5000

## Demo admin
- Username: `admin`
- Password: `ChangeMe123!`

Change the admin password before sharing/deploying. Set a strong random `SECRET_KEY` environment variable.
For public deployment, turn off Flask debug mode, use HTTPS, add CSRF protection and rate limiting, and review local laws.
This starter is for learning and private demos, not production use.
