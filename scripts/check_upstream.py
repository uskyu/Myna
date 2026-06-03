#!/usr/bin/env python3
import subprocess
import json
import urllib.request
import os

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

def check_upstream():
    # 获取最新代码
    run_git(["git", "fetch", "upstream"])
    
    # 获取本地和上游的commit hash
    local = run_git(["git", "rev-parse", "HEAD"])
    remote = run_git(["git", "rev-parse", "upstream/master"])
    
    if local == remote:
        print("代码已是最新")
        return
    
    # 获取新提交数量
    count = run_git(["git", "rev-list", "HEAD..upstream/master", "--count"])
    
    # 获取最新提交信息
    latest = run_git(["git", "log", "--oneline", "upstream/master", "-3"])
    
    # 发送提醒消息
    message = f"""🔔 **上游仓库有新更新！**

📊 新提交数: {count}
📝 最新提交:
```
{latest}
```

回复 **确认更新** 立即同步代码"""
    
    send_message(message)
    print(f"已发送更新提醒，新提交数: {count}")

if __name__ == "__main__":
    check_upstream()
