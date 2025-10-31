from adapters.rss_adapter import get_news_from_rss
import json

if __name__ == "__main__":
    items = get_news_from_rss(days_limit=30)
    print(f"Got {len(items)} items total")
    for i, it in enumerate(items[:10], 1):
        print(f"{i}. {it['Source']} | {it['Title']} | {it['PublishedAt']}")
    with open("rss_preview.json", "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    print("Wrote rss_preview.json")
