import os
import time
import datetime
import requests
from playwright.sync_api import sync_playwright

# === 1. 核心配置区（多页面任务清单） ===
# 在这里填入你想监控的所有页面，格式为 "名字": "网址"
TARGET_PAGES = {
    "主页": "https://it.plaud.ai/",
    "note": "https://it.plaud.ai/products/plaud-note-ai-voice-recorder",
    "notepro": "https://it.plaud.ai/products/plaud-note-pro",
    "notepin": "https://it.plaud.ai/products/plaud-notepin-wearable-ai-voice-recorder",
    "notepinS":"https://it.plaud.ai/products/plaud-notepin-s"
}

FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK")
GITHUB_REPO = os.getenv("GITHUB_REPOSITORY")
# =================================

today_str = datetime.datetime.now().strftime("%Y-%m-%d")
screenshots_data = {} # 用来临时记下每张图的名字，方便最后组装飞书消息

def scroll_to_bottom(page):
    """🤖 模拟真人缓慢滚动到底部，彻底触发所有懒加载图片"""
    print("    正在缓慢向下滚动以加载图片...")
    while True:
        # 每次往下滚一整个屏幕的高度
        page.evaluate("window.scrollBy(0, window.innerHeight);")
        # 停顿 1.5 秒，给服务器加载图片的时间，同时伪装真人阅读
        page.wait_for_timeout(1500) 
        
        # 检查是否已经滚到底了
        new_height = page.evaluate("document.body.scrollHeight")
        scrolled_y = page.evaluate("window.scrollY + window.innerHeight")
        
        if scrolled_y >= new_height:
            break # 到底了，退出循环
            
    # 截图前，把页面重新滚回最顶部，防止某些固定导航栏在长图中错位
    page.evaluate("window.scrollTo(0, 0);")
    page.wait_for_timeout(1000)

def take_screenshots():
    os.makedirs("screenshots", exist_ok=True)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        # 循环遍历我们配置的任务清单
        for page_name, url in TARGET_PAGES.items():
            print(f"\n🚀 开始抓取: {page_name} - {url}")
            
            # 去掉名字里的空格，防止生成的图片链接在飞书里打不开
            safe_name = page_name.replace(' ', '_')
            pc_path = f"screenshots/pc_{safe_name}_{today_str}.png"
            mobile_path = f"screenshots/mobile_{safe_name}_{today_str}.png"
            
            # 记录下来供飞书推送使用
            screenshots_data[page_name] = {"url": url, "pc": pc_path, "mobile": mobile_path}
            
            # === 1. PC 端抓取 ===
            print(f"  🖥️  正在截取 PC 端...")
            context_pc = browser.new_context(viewport={"width": 1920, "height": 1080})
            page_pc = context_pc.new_page()
            page_pc.goto(url, wait_until="networkidle")
            scroll_to_bottom(page_pc) # 调用我们的防懒加载法宝
            page_pc.screenshot(path=pc_path, full_page=True)
            context_pc.close()
            
            time.sleep(2) # 抓完PC端，喝口水休息2秒
            
            # === 2. 移动端抓取 ===
            print(f"  📱 正在截取 移动端...")
            iphone_13 = p.devices['iPhone 13 Pro']
            context_mobile = browser.new_context(**iphone_13)
            page_mobile = context_mobile.new_page()
            page_mobile.goto(url, wait_until="networkidle")
            scroll_to_bottom(page_mobile) # 调用我们的防懒加载法宝
            page_mobile.screenshot(path=mobile_path, full_page=True)
            context_mobile.close()
            
            # 抓完一个完整的页面后，强制休息 3 秒，防止被目标网站拉黑
            print(f"  💤 休息 3 秒钟防反爬...")
            time.sleep(3) 
            
        browser.close()

def send_to_feishu():
    # 动态构建飞书群的富文本排版
    feishu_content = [
        [{"tag": "text", "text": f"📅 抓取日期: {today_str}\n\n"}]
    ]
    
    # 把刚才抓的所有页面，一段一段拼接到消息体里
    for page_name, data in screenshots_data.items():
        pc_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{data['pc']}"
        mobile_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{data['mobile']}"
        
        feishu_content.append([{"tag": "text", "text": f"🎯 【{page_name}】"}])
        feishu_content.append([{"tag": "text", "text": f"🔗 链接: {data['url']}"}])
        feishu_content.append([{"tag": "a", "text": "👉 查看 [PC端] 高清原图", "href": pc_url}])
        feishu_content.append([{"tag": "a", "text": "👉 查看 [移动端] 高清原图", "href": mobile_url}])
        feishu_content.append([{"tag": "text", "text": "\n-----------------------\n"}])

    payload = {
        "msg_type": "post",
        "content": {
            "post": {
                "zh_cn": {
                    "title": "📊 核心页面双端监控日报",
                    "content": feishu_content
                }
            }
        }
    }
    
    response = requests.post(FEISHU_WEBHOOK, json=payload)
    print(f"\n✅ 飞书推送结果: {response.status_code} - {response.text}")

if __name__ == "__main__":
    take_screenshots()
    send_to_feishu()
