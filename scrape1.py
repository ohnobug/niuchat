import requests
import json
import time
from bs4 import BeautifulSoup

BASE_URL = "https://support.mehp.world"
TAG_API = f"{BASE_URL}/api-client/v1/article/tag"
LIST_API = f"{BASE_URL}/api-client/v1/tag/article/list"
DETAIL_API = f"{BASE_URL}/api-client/v1/article/info"

headers = {
    "User-Agent": "Mozilla/5.0",
    "Content-Type": "application/json"
}


def get_menu_ids():
    """获取所有二级菜单的 ID"""
    resp = requests.get(TAG_API, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    ids = [str(item["blog_id"]) for item in data.get("data", [])]
    return ids


def get_article_ids_by_menu(menu_id, lang_name="zh_TW"):
    """根据菜单 ID 获取文章 ID 列表"""
    page = 1
    page_size = 100
    article_ids = []

    while True:
        payload = {"blog_id": int(menu_id), "headerType": "json", "lang_name": lang_name}

        resp = requests.post(LIST_API, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("data", {}).get("list", [])
        if not items:
            break

        for item in items:
            article_data = item.get("article", {}).get("rows", [])
            for article in article_data:
                aid = article.get("aid")
                if aid:
                    article_ids.append(aid)
        if len(items) < page_size:
            break
        page += 1
        time.sleep(0.3)

    return article_ids


def get_article_detail(article_id, lang_name="zh_TW"):
    """获取文章内容"""
    payload = {"aid": int(article_id), "headerType": "json", "lang_name": lang_name}
    resp = requests.post(DETAIL_API, headers=headers, json=payload)
    resp.raise_for_status()
    data = resp.json()["data"]

    title = data["title"]
    html_content = data["content"]
    lang_name = data["lang_name"]

    # 将 HTML 转为纯文本
    soup = BeautifulSoup(html_content, "html.parser")
    text = soup.get_text(separator="\n", strip=True)

    return {
        "id": article_id,
        "title": title,
        "content": text,
        "lang_name": lang_name
    }


def crawl_all():
    # 支持的语言列表
    languages = ["en", "es_ES", "ko_KR", "pt_PT", "th_TH", "tr_TR", "vi_VN", "zh_TW"]
    
    all_data = []
    menu_ids = get_menu_ids()
    print(f"共发现 {len(menu_ids)} 个二级菜单")

    for lang_name in languages:
        print(f"正在抓取语言: {lang_name}")
        for menu_id in menu_ids:
            print(f"📂 处理菜单 ID: {menu_id}")
            article_ids = get_article_ids_by_menu(menu_id, lang_name)
            print(f"  - 发现文章 {len(article_ids)} 篇")

            for aid in article_ids:
                try:
                    detail = get_article_detail(aid, lang_name)
                    print(f"    ✓ 抓取文章 {aid}: {detail['title'][:30]}...")
                    all_data.append(detail)
                    time.sleep(0.5)
                except Exception as e:
                    print(f"    ✗ 抓取失败 {aid}: {e}")

    return all_data


if __name__ == "__main__":
    articles = crawl_all()
    with open("mehp_articles.json", "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 共保存 {len(articles)} 篇文章到 mehp_articles.json")
