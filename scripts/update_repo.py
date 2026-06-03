#!/usr/bin/env python3
import subprocess
import json
import urllib.request

# 配置
REPO_DIR = "/root/Ivy-myna"
MYNA_URL = "http://localhost:3455"
AGENT_API_KEY = "29a854fd69ef42a784bd95e9d0516a0b01e2c1ebbbc240a0a1ef346498129a43"
ROOM_ID = "a276fc28-3dd3-4632-a4c1-659fb1e537a4"

def run_git(cmd):
    result = subprocess.run(cmd, cwd=REPO_DIR, capture_output=True, text=True)
    return result.stdout.strip()

def send_message(text):
    data = json.dumps({
        "room_id": ROOM_ID,
        "text": text,
        "parse_mode": "markdown"
    }).encode()
    req = urllib.request.Request(
        f"{MYNA_URL}/bot{AGENT_API_KEY}/sendMessage",
        data=data,
        headers={"Content-Type": "application/json"}
    )
    try:
        resp = urllib.request.urlopen(req)
        return json.loads(resp.read().decode())
    except Exception as e:
        print(f"发送消息失败: {e}")
        return None

def update_repo():
    # 获取最新代码
    run_git(["git", "fetch", "upstream"])
    
    # 合并上游代码
    result = run_git(["git", "merge", "upstream/master"])
    
    # 推送到fork
    push_result = run_git(["git", "push", "origin", "master"])
    
    # 发送更新结果
    message = f"""✅ **代码已更新！**

📝 合并结果:
```
{result}
```

📤 推送结果:
```
{push_result}
```

本地开发版本将在下次重启后生效。"""
    
    send_message(message)
    print("代码更新完成")

if __name__ == "__main__":
    update_repo()
