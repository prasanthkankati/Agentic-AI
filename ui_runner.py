import asyncio
import json
import sys
from ui_crawler import crawl_ui_elements_async

if __name__ == "__main__":
    url = sys.argv[1]

    result = asyncio.run(crawl_ui_elements_async(url))

    # ✅ ONLY print JSON (no logs)
    print(json.dumps(result))