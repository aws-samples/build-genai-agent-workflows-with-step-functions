import asyncio
import httpx
import re
from bs4 import BeautifulSoup


async def read_page(page):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(page["href"])
            page_source = response.text
            soup = BeautifulSoup(page_source, "html.parser")
            page_text = soup.get_text()
            page_text = re.sub(r"\s+", " ", page_text)
            return {"url": page["href"], "title": page["title"], "text": page_text}
    except Exception as e:
        print(f"Error reading page: {page['href']}")
        print(e)
        return {"url": page["href"], "title": page["title"], "text": None}


async def read_all(pages):
    async with asyncio.TaskGroup() as tg:
        tasks = []
        for page in pages:
            task = tg.create_task(read_page(page))
            tasks.append(task)

        results = []
        total_size = 0
        for task in tasks:
            page = await task
            page_size = len(page["text"])
            if total_size + page_size <= 200000:
                results.append(page)
                total_size += page_size
                
        print(f"total text size = {total_size}")
        return results


def handler(event, context):
    pages = event["results"]
    return asyncio.run(read_all(pages))
