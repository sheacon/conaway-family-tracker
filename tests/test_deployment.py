"""Validate deployment config files to catch integration issues early.

These tests parse Dockerfile, fly.toml, .dockerignore, and GitHub Actions
workflows to ensure they stay consistent with each other and with uv-based
package management.
"""

import re
from pathlib import Path

ROOT = Path(__file__).parent.parent


class TestDockerfile:
    def setup_method(self):
        self.content = (ROOT / "Dockerfile").read_text()
        self.lines = self.content.splitlines()

    def test_cmd_uses_uv_run(self):
        cmd_lines = [l for l in self.lines if l.startswith("CMD")]
        assert cmd_lines, "Dockerfile must have a CMD"
        cmd = cmd_lines[-1]
        assert "uv run" in cmd, (
            f"CMD must use 'uv run' to access the virtualenv: {cmd}"
        )

    def test_cmd_runs_migrations_before_server(self):
        cmd_lines = [l for l in self.lines if l.startswith("CMD")]
        cmd = cmd_lines[-1]
        migrate_pos = cmd.find("db upgrade")
        gunicorn_pos = cmd.find("gunicorn")
        assert migrate_pos < gunicorn_pos, "Migrations must run before gunicorn"

    def test_sync_uses_no_dev_frozen(self):
        assert "uv sync --no-dev --frozen" in self.content

    def test_gunicorn_port_matches_fly_toml(self):
        port_match = re.search(r"0\.0\.0\.0:(\d+)", self.content)
        assert port_match, "Gunicorn bind port not found in Dockerfile"
        docker_port = port_match.group(1)
        fly_content = (ROOT / "fly.toml").read_text()
        assert f"internal_port = {docker_port}" in fly_content, (
            f"Dockerfile port {docker_port} doesn't match fly.toml internal_port"
        )

    def test_flask_app_env_set(self):
        assert "FLASK_APP" in self.content


class TestDockerignore:
    def setup_method(self):
        self.path = ROOT / ".dockerignore"
        self.content = self.path.read_text()
        self.entries = [l.strip() for l in self.content.splitlines() if l.strip()]

    def test_exists(self):
        assert self.path.exists()

    def test_excludes_venv(self):
        assert ".venv" in self.entries, (
            ".dockerignore must exclude .venv to prevent local venv "
            "from overriding container packages"
        )

    def test_excludes_env_file(self):
        assert ".env" in self.entries

    def test_excludes_local_db(self):
        assert "app.db" in self.entries

    def test_excludes_git(self):
        assert ".git" in self.entries


class TestFlyToml:
    def setup_method(self):
        self.content = (ROOT / "fly.toml").read_text()

    def test_auto_stop_uses_suspend(self):
        assert 'auto_stop_machines = "suspend"' in self.content, (
            "fly.toml should use 'suspend' not 'stop' to avoid cold start timeouts"
        )

    def test_auto_start_enabled(self):
        assert "auto_start_machines = true" in self.content

    def test_flask_app_env_set(self):
        assert "FLASK_APP" in self.content

    def test_database_url_points_to_persistent_volume(self):
        assert "/data/" in self.content, (
            "DATABASE_URL should point to the persistent volume at /data/"
        )

    def test_persistent_volume_mounted(self):
        assert 'destination = "/data"' in self.content


class TestGitHubWorkflow:
    def setup_method(self):
        self.path = ROOT / ".github" / "workflows" / "daily-notifications.yml"
        self.content = self.path.read_text()

    def test_exists(self):
        assert self.path.exists()

    def test_ssh_commands_use_uv_run(self):
        for line in self.content.splitlines():
            if "flyctl ssh" in line and "-C" in line:
                assert "uv run" in line, (
                    f"SSH command must use 'uv run' to access the virtualenv: "
                    f"{line.strip()}"
                )

    def test_wakes_machine_before_ssh(self):
        curl_pos = self.content.find("curl")
        ssh_pos = self.content.find("flyctl ssh")
        assert 0 <= curl_pos < ssh_pos, (
            "Workflow must wake the machine via curl before SSH commands"
        )

    def test_has_manual_trigger(self):
        assert "workflow_dispatch" in self.content

    def test_requires_fly_api_token(self):
        assert "FLY_API_TOKEN" in self.content
