import os
import datetime
import requests
from playwright.sync_api import sync_playwright

# === 配置区 ===
TARGET_URL = "https://it.plaud.ai/" # 替换为您要监控的真实网址
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK")
GITHUB_REPO = os.getenv("GITHUB_REPOSITORY") # 自动获取，例如: username/website-monitor-bot
# ============

# 生成带今天日期的文件名，避免缓存冲突
today_str = datetime.datetime.now().strftime("%Y-%m-%d")
pc_image_path = f"screenshots/pc_{today_str}.png"
mobile_image_path = f"screenshots/mobile_{today_str}.png"

def take_screenshots():
    # 创建存放图片的文件夹
    os.makedirs("screenshots", exist_ok=True)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        # 1. 截取 PC 端全图
        print("正在截取 PC 端...")
        context_pc = browser.new_context(viewport={"width": 1920, "height": 1080})
        page_pc = context_pc.new_page()
        page_pc.goto(TARGET_URL, wait_until="networkidle") # 等待网络空闲确保图加载完
        page_pc.screenshot(path=pc_image_path, full_page=True)
        context_pc.close()

        # 2. 截取 移动端 (iPhone 13 Pro) 全图
        print("正在截取 移动端...")
        iphone_13 = p.devices['iPhone 13 Pro']
        context_mobile = browser.new_context(**iphone_13)
        page_mobile = context_mobile.new_page()
        page_mobile.goto(TARGET_URL, wait_until="networkidle")
        page_mobile.screenshot(path=mobile_image_path, full_page=True)
        context_mobile.close()

        browser.close()

def send_to_feishu():
    # 构造能够直接在浏览器打开的 GitHub Raw 原始图片链接
    # 注意：这里默认您的主分支名为 main
    pc_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{pc_image_path}"
    mobile_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{mobile_image_path}"

    payload = {
        "msg_type": "post",
        "content": {
            "post": {
                "zh_cn": {
                    "title": "📊 网页双端监控日报已送达",
                    "content": [
                        [{"tag": "text", "text": f"🎯 监控目标: {TARGET_URL}\n"}],
                        [{"tag": "text", "text": f"📅 抓取日期: {today_str}\n\n"}],
                        [{"tag": "a", "text": "👉 点击查看 【PC 端】 高清完整截图", "href": pc_url}],
                        [{"tag": "text", "text": "\n"}],
                        [{"tag": "a", "text": "👉 点击查看 【移动端】 高清完整截图", "href": mobile_url}]
                    ]
                }
            }
        }
    }
    
    response = requests.post(FEISHU_WEBHOOK, json=payload)
    print(f"飞书推送结果: {response.status_code} - {response.text}")

if __name__ == "__main__":
    take_screenshots()
    send_to_feishu()
