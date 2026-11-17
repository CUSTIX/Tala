import re
from pathlib import Path

from django.conf import settings

ROOT = Path(settings.BASE_DIR)


def test_render_checks_livez_and_deploys_after_ci():
    blueprint = (ROOT / "render.yaml").read_text()
    assert "healthCheckPath: /livez/" in blueprint, "/healthz/ would wake the database every check"
    assert "autoDeployTrigger: checksPass" in blueprint
    assert "plan: free" in blueprint
    block = blueprint.split("key: DATABASE_URL")[1].split("- key")[0]
    assert "sync: false" in block, "DATABASE_URL must be set in the dashboard, not the repo"


def test_start_script_migrates_purges_then_serves():
    script = (ROOT / "bin" / "start.sh").read_text()
    assert script.index("migrate") < script.index("purge_demo") < script.index("gunicorn")
    assert "%(U)s" in script and "%(r)s" not in script, "access log must not record query strings"


def test_heartbeat_pings_livez_only_in_the_real_repo():
    workflow = (ROOT / ".github" / "workflows" / "keep-awake.yml").read_text()
    assert "/livez/" in workflow and "github.repository == 'CUSTIX/Tala'" in workflow


def test_env_file_is_never_committed_or_baked_in():
    assert ".env" in (ROOT / ".gitignore").read_text().split()
    assert ".env" in (ROOT / ".dockerignore").read_text().split()


def test_every_setting_read_from_env_is_documented():
    source = (ROOT / "config" / "settings.py").read_text()
    names = set(re.findall(r'os\.environ(?:\.get)?[\[(]"([A-Z_]+)"', source))
    names |= set(re.findall(r'env_(?:bool|list)\("([A-Z_]+)"', source))
    documented = (ROOT / ".env.example").read_text()
    assert names, "no settings found: the pattern is broken"
    assert not {n for n in names if n not in documented}
