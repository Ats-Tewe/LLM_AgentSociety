"""
test_smtp.py — Verify Gmail App Password works for sending emails.

Usage:
  GMAIL_USER="your-email@example.edu.tw" \
  GMAIL_APP_PASSWORD="abcdefghijklmnop" \
  uv run python scripts/test_smtp.py
"""
import sys
import os

if sys.prefix == sys.base_prefix:
    print("❌ Please run with uv: uv run python scripts/test_smtp.py", file=sys.stderr)
    sys.exit(1)

import json
import smtplib
from email.message import EmailMessage
from datetime import datetime

GMAIL_USER = os.environ.get("GMAIL_USER", "").strip()
APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "").strip().replace(" ", "")

if not GMAIL_USER or not APP_PASSWORD:
    print("❌ Missing env vars. Usage:", file=sys.stderr)
    print('   GMAIL_USER="..." GMAIL_APP_PASSWORD="..." uv run python scripts/test_smtp.py', file=sys.stderr)
    sys.exit(1)

print(f"📧 Sender / Recipient: {GMAIL_USER}")
print(f"🔑 App Password length: {len(APP_PASSWORD)} chars (expected 16)")
print()

# Simulate the actual report + env attachments that run_test.py will send
fake_report = {
    "run_timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
    "team": "TestStudent_B12345",
    "evaluation": {"metrics": {"RMSE": 1.234, "sentiment": 0.567}},
    "per_task_outputs": [{"task_id": 1, "stars": 4.0, "review": "sample"}],
    "errors": 0,
}
fake_env = {
    "git_branch": "main",
    "git_commit": "abc1234",
    "git_dirty": False,
    "python_version": "3.13.12",
    "model": "minimaxai/minimax-m2.7",
    "api_base": "https://integrate.api.nvidia.com/v1",
    "platform": "darwin",
}

report_bytes = json.dumps(fake_report, indent=2, ensure_ascii=False).encode("utf-8")
env_bytes    = json.dumps(fake_env,    indent=2, ensure_ascii=False).encode("utf-8")

msg = EmailMessage()
msg["Subject"] = f"[AgentSociety SMTP Test w/ Attachments] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
msg["From"] = GMAIL_USER
msg["To"] = GMAIL_USER
msg.set_content(
    "If you see this email AND can open both attachments, the full email flow is working.\n\n"
    "Attachments:\n"
    "  1. fake_report.json — simulates run_test.py's evaluation report\n"
    "  2. fake_env.json    — simulates run_test.py's environment snapshot\n\n"
    f"Report size: {len(report_bytes)} bytes\n"
    f"Env size:    {len(env_bytes)} bytes\n"
)
msg.add_attachment(report_bytes, maintype="application", subtype="json", filename="fake_report.json")
msg.add_attachment(env_bytes,    maintype="application", subtype="json", filename="fake_env.json")

try:
    print("⏳ Connecting to smtp.gmail.com:465 ...")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
        print("⏳ Logging in ...")
        server.login(GMAIL_USER, APP_PASSWORD)
        print("⏳ Sending message ...")
        server.send_message(msg)
    print()
    print("✅ Email sent successfully! Check your inbox.")
except smtplib.SMTPAuthenticationError as e:
    print(f"\n❌ Authentication failed: {e}", file=sys.stderr)
    print("   Possible causes:", file=sys.stderr)
    print("   - App Password incorrect or revoked", file=sys.stderr)
    print("   - 2-Step Verification not enabled", file=sys.stderr)
    print("   - School Workspace blocks App Passwords", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"\n❌ Unexpected error: {type(e).__name__}: {e}", file=sys.stderr)
    sys.exit(1)
