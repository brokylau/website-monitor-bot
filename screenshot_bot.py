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
    """🧹 清理 7 天前的旧图"""
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
                    os.remove(os.path.join(folder_path, filename))
                    print(f"  🗑️ 已删除过期文件: {filename}")
                    deleted_count += 1
            except ValueError:
                pass 
                
    if deleted_count == 0:
        print("  ✨ 没有需要清理的旧图。")
    else:
        print(f"  ✅ 清理完成！删除了 {deleted_count} 张旧图。")

def scroll_to_bottom(page):
    """🤖 模拟真人缓慢滚动到底部"""
    print("    正在向下滚动加载图片...")
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
    
    # 🌟 核心探针代码：接收 is_home 参数，动态决定是否检查 Banner
    js_check_script = """
    (is_home) => {
        let status = { nav_display: 'MISSING', banner_ratio: 0, banner_missing: true };

        // 1. 获取导航栏状态 (所有页面都要查)
        let navToggle = document.querySelector('button[data-action="toggle-nav"]');
        if (navToggle) {
            status.nav_display = window.getComputedStyle(navToggle).display;
        }

        // 2. 获取 Banner 真实宽高比例 (仅首页查)
        if (is_home) {
            let banner = document.querySelector('.banner__media');
            if (banner) {
                let rect = banner.getBoundingClientRect();
                if (rect.height > 0) {
                    status.banner_ratio = rect.width / rect.height;
                    status.banner_missing = false;
                }
            }
        }
        return status;
    }
    """

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        for page_name, url in TARGET_PAGES.items():
            print(f"\n🚀 开始抓取: {page_name} - {url}")
            
            safe_name = page_name.replace(' ', '_')
            pc_path = f"screenshots/pc_{safe_name}_{today_str}.png"
            mobile_path = f"screenshots/mobile_{safe_name}_{today_str}.png"
            
            # 判断当前页面是否为主页
            is_home_page = (page_name == "主页")
            
            # === 1. PC 端抓取与检测 ===
            print(f"  🖥️  正在截取 PC 端并执行检测...")
            context_pc = browser.new_context(viewport={"width": 1920, "height": 1080})
            page_pc = context_pc.new_page()
            page_pc.goto(url, wait_until="networkidle")
            scroll_to_bottom(page_pc) 
            # 传入 is_home_page 参数
            pc_result = page_pc.evaluate(js_check_script, is_home_page)
            page_pc.screenshot(path=pc_path, full_page=True)
            context_pc.close()
            
            time.sleep(2)
            
            # === 2. 移动端抓取与检测 ===
            print(f"  📱 正在截取 移动端并执行检测...")
            iphone_13 = p.devices['iPhone 13 Pro']
            context_mobile = browser.new_context(**iphone_13)
            page_mobile = context_mobile.new_page()
            page_mobile.goto(url, wait_until="networkidle")
            scroll_to_bottom(page_mobile) 
            # 传入 is_home_page 参数
            mobile_result = page_mobile.evaluate(js_check_script, is_home_page)
            page_mobile.screenshot(path=mobile_path, full_page=True)
            context_mobile.close()
            
            screenshots_data[page_name] = {
                "url": url, 
                "pc_path": pc_path, 
                "mobile_path": mobile_path,
                "pc_result": pc_result,
                "mobile_result": mobile_result
            }
            
            print(f"  💤 休息 3 秒...")
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

# ==== 飞书文本格式化辅助函数 ====
def format_status_text(device, result, page_name):
    is_error = False
    
    # 1. 导航栏判断
    if device == 'pc':
        nav_ok = (result['nav_display'] == 'none')
        nav_str = "导航栏toggle隐藏 ✅" if nav_ok else f"导航栏toggle状态异常({result['nav_display']}) ❌"
    else: # mobile
        nav_ok = (result['nav_display'] not in ['none', 'MISSING'])
        nav_str = "导航栏toggle加载正常 ✅" if nav_ok else "导航栏toggle隐藏/丢失 ❌"
        
    if not nav_ok: is_error = True

    # 2. Banner 判断 (仅首页附加此文本)
    banner_str = ""
    if page_name == "主页":
        if result['banner_missing']:
            banner_str = "，banner丢失 ❌"
            is_error = True
        else:
            ratio = result['banner_ratio']
            if device == 'pc':
                banner_ok = (ratio > 1.2) # PC应该是横图
            else:
                banner_ok = (ratio <= 1.2) # 手机应该是竖图
                
            banner_icon = "✅" if banner_ok else "❌"
            banner_str = f"，banner比例为{ratio:.2f} {banner_icon}"
            if not banner_ok: is_error = True

    # 3. 最终文本拼接
    if device == 'pc':
        title = "pc端渲染正常" if not is_error else "pc端渲染异常"
    else:
        title = "移动端渲染正常" if not is_error else "移动端渲染异常"
        
    return f"{title}（{nav_str}{banner_str}）", is_error

def send_to_feishu():
    folder_size_mb = get_folder_size("screenshots")
    
    md_text = f"**🗓️ 抓取日期:** {today_str}\n"
    md_text += f"**💽 图库占用:** {folder_size_mb:.2f} MB / 1000 MB *(已自动清理7天前旧图)*\n\n---\n\n"
    
    has_global_error = False

    for page_name, data in screenshots_data.items():
        pc_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{data['pc_path']}"
        mobile_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{data['mobile_path']}"
        page_url = data['url']
        
        # 使用辅助函数格式化双端文案，传入 page_name 判定是否是主页
        pc_text, pc_is_error = format_status_text('pc', data['pc_result'], page_name)
        mb_text, mb_is_error = format_status_text('mobile', data['mobile_result'], page_name)
        
        if pc_is_error or mb_is_error:
            has_global_error = True

        md_text += f"🎯 **【{page_name}】**\n"
        md_text += f"🖥️ **PC端:** {pc_text}\n"
        md_text += f"📱 **移动端:** {mb_text}\n"
        md_text += f"👉 [🌐 线上页面]({page_url}) ｜ [💻 PC端截图]({pc_url}) ｜ [📱 移动端截图]({mobile_url})\n\n"

    card_color = "red" if has_global_error else "green"

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
