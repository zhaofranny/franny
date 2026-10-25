import json
import platform
import shutil
import sys
from pathlib import Path
from . import VERSION

def inspect(base):
    from playwright.sync_api import sync_playwright
    base=Path(base)
    with sync_playwright() as p:
        bundled=Path(p.chromium.executable_path)
    policy=Path('/etc/codex/network-policy.json')
    network='not_inspected_on_this_host'
    if policy.exists():
        data=json.loads(policy.read_text())
        rules=data.get('http_network_policy',{})
        if rules.get('type')=='restricted':
            network='allowed' if any(r.get('host')=='creator.xiaohongshu.com' for r in rules.get('egress_rules',[])) else 'managed_environment_does_not_allow_creator.xiaohongshu.com'
    return {'version':VERSION,'os':platform.system(),'mac_verified':platform.system()=='Darwin','python':platform.python_version(),'python_supported':sys.version_info>=(3,10),'bundled_chromium_installed':bundled.is_file(),'system_chromium_for_tests':bool(shutil.which('chromium')),'browser_profile_present':(base/'.local'/'browser_profile').is_dir(),'network_policy':network,'live_publication_tested':False,'message':'当前检查只覆盖运行它的机器；Linux结果不能当作用户Mac的检查。'}

if __name__=='__main__':
    print(json.dumps(inspect(Path(__file__).resolve().parents[1]),ensure_ascii=False,indent=2))
