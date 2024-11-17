import asyncio, json, os
from crawl4ai import AsyncWebCrawler
import re
from urllib.parse import urljoin
from langchain_groq import ChatGroq
from dotenv import load_dotenv, find_dotenv
from urllib.error import URLError
from urllib.parse import urlparse

def validate_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False

projectname = input("Enter project name: ")
base_url = input("Enter base url: ")

# Input validation
if not validate_url(base_url):
    print("Invalid base URL. Please enter a valid URL.")
    exit(1)

filename = "./" + projectname + "/" + projectname + ".md"

pattern = re.compile(r'\[([^\]]+)\]\((?!http)([^\)]+)\)')

def convert_relative_links(content, base_url):
    return pattern.sub(lambda match: f"[{match.group(1)}]({urljoin(base_url, match.group(2))})", content)

async def crawl(url_link, filename, is_base_url):
    try:
        async with AsyncWebCrawler(verbose=False) as crawler:
            result = await crawler.arun(url=url_link)
            if is_base_url:
               markdown_content = result.markdown            
            else:
                markdown_content = result.fit_markdown.replace('    ```','```')

            md_with_absolute_links = convert_relative_links(markdown_content, base_url)
            os.makedirs(projectname, exist_ok=True)
            with open(filename, "w", encoding='utf-8') as f:
                f.write(md_with_absolute_links)
    except URLError as e:
        print(f"Error crawling {url_link}: {e}")
    except Exception as e:
        print(f"An unexpected error occurred while crawling {url_link}: {e}")


asyncio.run(crawl(url_link=base_url, filename=filename, is_base_url=True))

with open(filename, "r", encoding='utf-8') as f:
    contents = f.read()

load_dotenv(find_dotenv())
Groq_Token = os.getenv('GROQ_API_KEY')

llm = ChatGroq(groq_api_key=Groq_Token, model_name="gemma2-9b-it")
result = llm.invoke("Extract all internal links from following extracted webpage. Provide suitable title if not present. Url should be absolute url and start with http \n Extracted Webpage: " + contents)
uncleaned_json_result = llm.invoke(f"Convert the text to json like: "
                                   '''{
                                      "links": [
                                          {
                                          "title": "Introduction",
                                          "link": "/introduction"
                                          },
                                           ]
                                      }
                                  '''
                                   "Output should only have json. Do not provide anything else like introduction, summary etc."
                                   "Content: " + result.content)

def clean_json_text(text):
    text = text.replace('```json', '').replace('```', '').strip()
    return text

cleaned_json = clean_json_text(uncleaned_json_result.content)

with open("./" + projectname + "/links.json", "w", encoding='utf-8') as f:
    f.write(cleaned_json)  # links.json created


with open("./" + projectname + "/links.json", 'r', encoding='utf-8') as f:
    links_data = json.load(f)  # links.json opened to iterate

for link in links_data['links']:
    try:
        filename = "./" + projectname + "/" + f"{link['title'].replace('/', '_').replace(' ', '_').replace(':', '_')}" + ".md"
        url = link["link"]
        asyncio.run(crawl(url_link=url, filename=filename, is_base_url=False))
    except Exception as e:
        print(f"Could not process {url}: {e}")
