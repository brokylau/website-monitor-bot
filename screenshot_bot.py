import os
import time
import datetime
import requests
import re
import html
import json
import hashlib
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo
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

# === AI HOT RSS 配置 ===
AIHOT_FEED_URL = "https://aihot.virxact.com/feed.xml"
AIHOT_HOME_URL = "https://aihot.virxact.com/"
AIHOT_STATE_FILE = os.getenv("AIHOT_STATE_FILE", "aihot_state.json")
def get_int_env(name, default):
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError:
        print(f"⚠️ 环境变量 {name}={value} 不是有效数字，使用默认值 {default}")
        return default

AIHOT_MAX_ITEMS = get_int_env("AIHOT_MAX_ITEMS", 10)
CN_TZ = ZoneInfo("Asia/Shanghai")

AIHOT_ALLOWED_CATEGORIES = {
    "模型",
    "产品更新",
    "行业动态",
    "论文/研究",
    "教程/实践",
    "智能体",
    "MCP/工具",
    "开源/仓库",
    "图像生成",
    "视频",
    "多模态",
    "编码",
    "推理",
    "安全/对齐",
    "部署/工程",
    "数据/训练",
    "评测/基准",
}
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

    js_check_script = """
    (is_home) => {
        let status = { nav_display: 'MISSING', banner_ratio: 0, banner_missing: true };

        let navToggle = document.querySelector('button[data-action="toggle-nav"]');
        if (navToggle) {
            status.nav_display = window.getComputedStyle(navToggle).display;
        }

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
        # 🟢 优化 1：启动浏览器时，禁用自动化控制特征
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled", # 核心防封参数
                "--no-sandbox",
                "--disable-setuid-sandbox"
            ]
        )

        for page_name, url in TARGET_PAGES.items():
            print(f"\n🚀 开始抓取: {page_name} - {url}")

            safe_name = page_name.replace(' ', '_')
            pc_path = f"screenshots/pc_{safe_name}_{today_str}.png"
            mobile_path = f"screenshots/mobile_{safe_name}_{today_str}.png"

            is_home_page = (page_name == "主页")

            print(f"  🖥️  正在截取 PC 端并执行检测...")
            
            # 🟢 优化 2：PC 端强制使用真实的 User-Agent 和 常见浏览器的请求头
            context_pc = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                extra_http_headers={"Accept-Language": "en-US,en;q=0.9"}
            )
            page_pc = context_pc.new_page()
            
            # 🟢 优化 3：在页面加载前注入 JS，彻底抹除 window.navigator.webdriver 机器人特征
            page_pc.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            page_pc.goto(url, wait_until="networkidle")
            scroll_to_bottom(page_pc)
            pc_result = page_pc.evaluate(js_check_script, is_home_page)
            page_pc.screenshot(path=pc_path, full_page=True)
            context_pc.close()

            time.sleep(2)

            print(f"  📱 正在截取 移动端并执行检测...")
            iphone_13 = p.devices['iPhone 13 Pro']
            
            # 移动端补充请求头
            context_mobile = browser.new_context(
                **iphone_13,
                extra_http_headers={"Accept-Language": "en-US,en;q=0.9"}
            )
            page_mobile = context_mobile.new_page()
            
            # 移动端同样抹除机器人特征
            page_mobile.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            page_mobile.goto(url, wait_until="networkidle")
            scroll_to_bottom(page_mobile)
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

    if device == 'pc':
        nav_ok = (result['nav_display'] == 'none')
        nav_str = "导航栏toggle隐藏 ✅" if nav_ok else f"导航栏toggle状态异常({result['nav_display']}) ❌"
    else:
        nav_ok = (result['nav_display'] not in ['none', 'MISSING'])
        nav_str = "导航栏toggle加载正常 ✅" if nav_ok else "导航栏toggle隐藏/丢失 ❌"

    if not nav_ok:
        is_error = True

    banner_str = ""
    if page_name == "主页":
        if result['banner_missing']:
            banner_str = "，banner丢失 ❌"
            is_error = True
        else:
            ratio = result['banner_ratio']
            if device == 'pc':
                banner_ok = (ratio > 1.2)
            else:
                banner_ok = (ratio <= 1.2)

            banner_icon = "✅" if banner_ok else "❌"
            banner_str = f"，banner比例为{ratio:.2f} {banner_icon}"
            if not banner_ok:
                is_error = True

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

# ==== AI HOT RSS 功能 ====
def strip_html(text):
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def truncate_text(text, max_len=180):
    if not text:
        return ""
    return text if len(text) <= max_len else text[:max_len].rstrip() + "..."

def xml_local_name(tag):
    return tag.split("}", 1)[-1] if "}" in tag else tag

def get_child_text(node, *names):
    names = set(names)
    for child in list(node):
        if xml_local_name(child.tag) in names and child.text:
            return child.text.strip()
    return ""

def get_child_attr(node, child_name, attr_name):
    for child in list(node):
        if xml_local_name(child.tag) == child_name:
            value = child.attrib.get(attr_name)
            if value:
                return value.strip()
    return ""

def get_categories(node):
    categories = []
    for child in list(node):
        local = xml_local_name(child.tag)
        if local == "category":
            if child.text and child.text.strip():
                categories.append(child.text.strip())
            elif child.attrib.get("term"):
                categories.append(child.attrib["term"].strip())
    return categories

def parse_feed_datetime(value):
    if not value:
        return None

    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt.astimezone(CN_TZ)
    except Exception:
        pass

    try:
        normalized = value.replace("Z", "+00:00")
        dt = datetime.datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt.astimezone(CN_TZ)
    except Exception:
        return None

def extract_aihot_score(text):
    if not text:
        return 0

    patterns = [
        r"精选\s*(\d{1,3})",
        r"score[：:\s]+(\d{1,3})",
        r"评分[：:\s]+(\d{1,3})",
        r"热度[：:\s]+(\d{1,3})",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return int(match.group(1))

    return 0

def infer_aihot_categories(text, rss_categories):
    categories = list(rss_categories or [])

    for category in AIHOT_ALLOWED_CATEGORIES:
        if category in text and category not in categories:
            categories.append(category)

    return categories

def make_aihot_item_id(item):
    raw = item.get("guid") or item.get("link") or f"{item.get('title', '')}|{item.get('published_raw', '')}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def load_aihot_state():
    if not os.path.exists(AIHOT_STATE_FILE):
        return {}
    try:
        with open(AIHOT_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ 读取 AI HOT 状态文件失败，将按首次运行处理: {e}")
        return {}

def save_aihot_state(latest_item):
    state = {
        "latest_item_id": latest_item["item_id"],
        "latest_title": latest_item.get("title", ""),
        "latest_link": latest_item.get("link", ""),
        "latest_published_at": latest_item["published_at"].isoformat() if latest_item.get("published_at") else "",
        "updated_at": datetime.datetime.now(CN_TZ).isoformat(),
    }
    with open(AIHOT_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def fetch_aihot_items():
    response = requests.get(
        AIHOT_FEED_URL,
        timeout=20,
        headers={"User-Agent": "plaud-monitor/1.0"}
    )
    response.raise_for_status()

    root = ET.fromstring(response.content)

    entries = [node for node in root.iter() if xml_local_name(node.tag) == "item"]
    if not entries:
        entries = [node for node in root.iter() if xml_local_name(node.tag) == "entry"]

    parsed_items = []

    for entry in entries:
        title = get_child_text(entry, "title")
        link = get_child_text(entry, "link") or get_child_attr(entry, "link", "href")
        guid = get_child_text(entry, "guid", "id")

        description = (
            get_child_text(entry, "description")
            or get_child_text(entry, "summary")
            or get_child_text(entry, "content")
        )

        pub_date_raw = (
            get_child_text(entry, "pubDate")
            or get_child_text(entry, "published")
            or get_child_text(entry, "updated")
        )

        clean_title = strip_html(title)
        clean_description = strip_html(description)
        rss_categories = get_categories(entry)
        searchable_text = f"{clean_title} {clean_description} {' '.join(rss_categories)}"

        item = {
            "guid": guid,
            "title": clean_title,
            "link": link,
            "description": truncate_text(clean_description, 180),
            "published_raw": pub_date_raw,
            "published_at": parse_feed_datetime(pub_date_raw),
            "categories": infer_aihot_categories(searchable_text, rss_categories)[:5],
            "score": extract_aihot_score(searchable_text),
        }
        item["item_id"] = make_aihot_item_id(item)
        parsed_items.append(item)

    print(f"\n📰 AI HOT RSS 拉取完成：当前 feed 条目 {len(parsed_items)}")
    return parsed_items[:50]

def get_aihot_incremental_items(all_items):
    state = load_aihot_state()
    last_latest_id = state.get("latest_item_id")

    if not all_items:
        return [], "empty", 0

    if not last_latest_id:
        return all_items, "first_run_latest_50", len(all_items)

    incremental = []
    found_checkpoint = False

    for item in all_items:
        if item["item_id"] == last_latest_id:
            found_checkpoint = True
            break
        incremental.append(item)

    if found_checkpoint:
        return incremental, "since_last_checkpoint", len(incremental)

    return all_items, "checkpoint_missing_latest_50", len(all_items)

def filter_aihot_items(items):
    if not items:
        return []

    ranked_items = sorted(
        items,
        key=lambda item: (
            item.get("score", 0),
            item.get("published_at") or datetime.datetime.min.replace(tzinfo=CN_TZ)
        ),
        reverse=True
    )

    return ranked_items[:AIHOT_MAX_ITEMS]

def format_aihot_item(item, index):
    title = item["title"] or "未命名资讯"
    link = item["link"]
    published_at = item["published_at"]
    time_text = published_at.strftime("%m-%d %H:%M") if published_at else "时间未知"
    score = item.get("score", 0)
    categories = item.get("categories", [])
    tags = " / ".join(categories[:4]) if categories else "未分类"

    if link:
        md = f"**{index}. [{title}]({link})**\n"
    else:
        md = f"**{index}. {title}**\n"

    md += f"时间：{time_text} ｜ 评分：{score} ｜ 分类：{tags}\n"

    if item.get("description"):
        md += f"{item['description']}\n"

    return md

def send_aihot_to_feishu():
    try:
        all_items = fetch_aihot_items()
        candidate_items, mode, update_count = get_aihot_incremental_items(all_items)
        selected_items = filter_aihot_items(candidate_items)
        beijing_today_str = datetime.datetime.now(CN_TZ).strftime("%Y-%m-%d")

        md_text = f"**🗓️ 日期:** {beijing_today_str}\n"
        md_text += f"**📡 来源:** [AI HOT RSS]({AIHOT_FEED_URL})\n"
        md_text += f"**🧭 抓取逻辑:** 最新 50 条；以上次最新条目为断点\n"
        md_text += f"**📌 本周期新增:** {update_count} 条"

        if mode == "checkpoint_missing_latest_50":
            md_text += "（断点未找到，已回退使用最新 50 条）"
        elif mode == "first_run_latest_50":
            md_text += "（首次运行，使用最新 50 条）"
        elif mode == "empty":
            md_text += "（feed 为空）"

        md_text += "\n"
        md_text += f"**🎚️ 筛选:** 按评分排序，展示前 {AIHOT_MAX_ITEMS} 条\n"
        md_text += f"**📬 本次展示:** {len(selected_items)} 条\n\n---\n\n"

        if selected_items:
            for index, item in enumerate(selected_items, start=1):
                md_text += format_aihot_item(item, index)
                md_text += "\n"
            card_color = "blue"
        else:
            md_text += "本周期没有符合当前评分和分类条件的资讯。\n\n"
            card_color = "grey"

        md_text += "---\n"
        md_text += f"查看更多：[AI HOT 精选]({AIHOT_HOME_URL}) ｜ [RSS]({AIHOT_FEED_URL})\n"

        payload = {
            "msg_type": "interactive",
            "card": {
                "config": {
                    "wide_screen_mode": True
                },
                "header": {
                    "template": card_color,
                    "title": {
                        "content": "📰 AI HOT 每日精选资讯",
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

        response = requests.post(FEISHU_WEBHOOK, json=payload, timeout=20)
        print(f"\n✅ AI HOT 飞书推送结果: {response.status_code} - {response.text}")

        if response.status_code == 200 and all_items:
            save_aihot_state(all_items[0])
            print(f"✅ 已更新 AI HOT 断点: {all_items[0].get('title', '')}")

    except Exception as e:
        print(f"\n⚠️ AI HOT 资讯推送失败，不影响页面监控日报: {e}")

if __name__ == "__main__":
    try:
        cleanup_old_screenshots(days_to_keep=7)
        take_screenshots()
        send_to_feishu()
    except Exception as e:
        print(f"\n⚠️ 页面监控日报失败，不影响 AI HOT 资讯推送: {e}")

    send_aihot_to_feishu()

