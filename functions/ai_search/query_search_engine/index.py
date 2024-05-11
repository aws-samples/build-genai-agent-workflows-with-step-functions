import asyncio
from duckduckgo_search import AsyncDDGS

async def aget_results(word, results, unique_hrefs):
    keywords = word + " filetype:html"
    search_results = await AsyncDDGS(proxies=None).text(keywords, max_results=3)

    for result in search_results:
        if result['href'] not in unique_hrefs:
            results.append(result)
            unique_hrefs.add(result['href'])

async def search(keywords):
    unique_hrefs = set()
    results = []
    tasks = [aget_results(w, results, unique_hrefs) for w in keywords]
    await asyncio.gather(*tasks)
    return results

def handler(event, context):

    return asyncio.run(search(event["keywords"]))
