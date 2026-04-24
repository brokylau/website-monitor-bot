import os
import time
import datetime
import requests
import re 
from playwright.sync_api import sync_playwright

# === 1. 核心配置区（多页面任务清单） ===
TARGET_PAGES = {
    "主页": "https://it.plaud.ai/",
    "note": "https://it.plaud.ai/products/plaud-note-ai-voice-recorder",
    "notepro": "https://it.plaud.ai/products/plaud-note-pro",
    "notepin": "https://it.plaud.ai/products/plaud-notepin-wearable-ai-voice-recorder",
    "notepinS": "https://it.plaud.ai/products/plaud-notepin-s"
}

FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK")
GITHUB_REPO = os.getenv("GITHUB_REPOSITORY")
# =================================

today_str = datetime.datetime.now().strftime("%Y-%m-%d")
screenshots_data = {}

def cleanup_old_screenshots(folder_path="screenshots", days_to_keep=7):
    """🧹 核心清理函数：通过提取文件名里的日期，删除 7 天前的旧图"""
    print(f"\n🔍 开始检查并清理 {days_to_keep} 天前的旧截图...")
    if not os.path.exists(folder_path):
        return
        
    today = datetime.datetime.now()
    deleted_count = 0
    date_pattern = re.compile(r'_(\d{4}-\d{2}-\d{2})\.png$')
    
    for filename in os.listdir(folder_path):
        match = date_pattern.search(filename)
        if match:
            file_date_str = match.group(1)
            try:
                file_date = datetime.datetime.strptime(file_date_str, "%Y-%m-%d")
                delta = today - file_date
                
                if delta.days > days_to_keep:
                    file_path = os.path.join(folder_path, filename)
                    os.remove(file_path)
                    print(f"  🗑️ 已删除过期文件: {filename}")
                    deleted_count += 1
            except ValueError:
                pass 
                
    if deleted_count == 0:
        print("  ✨ 没有发现需要清理的旧图。")
    else:
        print(f"  ✅ 清理完成！共删除了 {deleted_count} 张旧图。")

def scroll_to_bottom(page):
    """🤖 模拟真人缓慢滚动到底部，彻底触发所有懒加载图片"""
    print("    正在缓慢向下滚动以加载图片...")
    while True:
        page.evaluate("window.scrollBy(0, window.innerHeight);")
        page.wait_for_timeout(1500) 
        
        new_height = page.evaluate("document.body.scrollHeight")
        scrolled_y = page.evaluate("window.scrollY + window.innerHeight")
        
        if scrolled_y >= new_height:
            break
            
    page.evaluate("window.scrollTo(0, 0);")
    page.wait_for_timeout(1000)

def take_screenshots():
    os.makedirs("screenshots", exist_ok=True)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        for page_name, url in TARGET_PAGES.items():
            print(f"\n🚀 开始抓取: {page_name} - {url}")
            
            safe_name = page_name.replace(' ', '_')
            pc_path = f"screenshots/pc_{safe_name}_{today_str}.png"
            mobile_path = f"screenshots/mobile_{safe_name}_{today_str}.png"
            
            # === 1. PC 端抓取 ===
            print(f"  🖥️  正在截取 PC 端...")
            context_pc = browser.new_context(viewport={"width": 1920, "height": 1080})
            page_pc = context_pc.new_page()
            page_pc.goto(url, wait_until="networkidle")
            scroll_to_bottom(page_pc) 
            page_pc.screenshot(path=pc_path, full_page=True)
            context_pc.close()
            
            time.sleep(2)
            
            # === 2. 移动端抓取 ===
            print(f"  📱 正在截取 移动端...")
            iphone_13 = p.devices['iPhone 13 Pro']
            context_mobile = browser.new_context(**iphone_13)
            page_mobile = context_mobile.new_page()
            page_mobile.goto(url, wait_until="networkidle")
            scroll_to_bottom(page_mobile) 
            
            # 🌟 核心新增：向移动端注入 JS 判断导航栏状态
            js_check_script = """
            () => {
                var navToggle = document.querySelector('div[data-action="toggle-nav"]');
                if (!navToggle) return 'MISSING';
                return window.getComputedStyle(navToggle).display;
            }
            """
            nav_display_status = page_mobile.evaluate(js_check_script)
            
            # 判断逻辑：如果是 none，说明移动端加载了 PC 版
            is_mobile_error = (nav_display_status == 'none')
            if is_mobile_error:
                print(f"    🚨 警告：检测到移动端渲染了 PC 样式！(display: none)")
            else:
                print(f"    ✅ 移动端渲染检查正常。(display: {nav_display_status})")

            page_mobile.screenshot(path=mobile_path, full_page=True)
            context_mobile.close()
            
            # 将判定结果存入字典，留给飞书推送使用
            screenshots_data[page_name] = {
                "url": url, 
                "pc": pc_path, 
                "mobile": mobile_path,
                "is_mobile_error": is_mobile_error,
                "nav_status": nav_display_status
            }
            
            print(f"  💤 休息 3 秒钟防反爬...")
            time.sleep(3) 
            
        browser.close()

def get_folder_size(folder_path="screenshots"):
    """计算文件夹总大小，返回 MB"""
    total_size = 0
    if not os.path.exists(folder_path):
        return 0
    for dirpath, dirnames, filenames in os.walk(folder_path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if not os.path.islink(fp):
                total_size += os.path.getsize(fp)
    return total_size / (1024 * 1024)

def send_to_feishu():
    folder_size_mb = get_folder_size("screenshots")
    
    # 构造 Markdown 文本
    md_text = f"**🗓️ 抓取日期:** {today_str}\n"
    md_text += f"**💽 图库占用:** {folder_size_mb:.2f} MB / 1000 MB *(已自动清理7天前旧图)*\n\n---\n\n"
    
    has_global_error = False

    for page_name, data in screenshots_data.items():
        pc_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{data['pc']}"
        mobile_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{data['mobile']}"
        page_url = data['url']
        
        # 根据 JS 检查结果设置对应的文案和表情
        if data["is_mobile_error"]:
            has_global_error = True
            status_text = "🚨 **异常预警：移动端呈现了PC版代码！**"
        elif data["nav_status"] == 'MISSING':
            status_text = "⚠️ **元素丢失：未找到导航栏进行验证**"
        else:
            status_text = "✅ **移动端渲染正常**"

        md_text += f"🎯 **【{page_name}】** {status_text}\n"
        md_text += f"👉 [🌐 线上页面]({page_url}) ｜ [💻 PC端截图]({pc_url}) ｜ [📱 移动端截图]({mobile_url})\n\n"

    # 根据是否有异常，决定卡片头部的颜色（有报错就红，没报错就绿）
    card_color = "red" if has_global_error else "green"

    # 使用 Interactive Card 高级格式
    payload = {
        "msg_type": "interactive",
        "card": {
            "config": {
                "wide_screen_mode": True
            },
            "header": {
                "template": card_color,
                "title": {
                    "content": "📊 核心页面双端监控日报",
                    "tag": "plain_text"
                }
            },
            "elements": [
                {
                    "tag": "markdown",
                    "content": md_text
                }
            ]
        }
    }
    
    response = requests.post(FEISHU_WEBHOOK, json=payload)
    print(f"\n✅ 飞书推送结果: {response.status_code} - {response.text}")

if __name__ == "__main__":
    cleanup_old_screenshots(days_to_keep=7)
    take_screenshots()
    send_to_feishu()
