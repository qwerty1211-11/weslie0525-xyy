import asyncio
import json
import os
import pandas as pd
from crawl4ai import AsyncWebCrawler, BrowserConfig,CrawlerRunConfig, CacheMode,LLMConfig
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy
url=""
# 第二段：
async def simple_demo():
    # 1.BrowserConfig 浏览器配置
    browser_config = BrowserConfig(
        headless=True, # True(无头模式，即不打开浏览器窗口) False(打开浏览器窗口)
    )
    # LLMConfig LLM配置
    # 3.1 找哪个表哥和门禁卡
    llm_config= LLMConfig(
        provider='deepseek/deepseek-chat',
        api_token=os.getenv("")
    )
    # 3.2 保存ai生成的内容提取规则
    strategy=JsonCssExtractionStrategy.generate_schema(
        url=url,
        llm_config=llm_config,
        instruction="提取页面所有二手车信息，每条数据包含：车辆标题、售价、上牌年份、行驶里程，只返回车辆列表，过滤广告无关内容"
    )
    print(strategy)
    # 2.CrawlerRunConfig 爬虫运行配置
    crawler_run_config = CrawlerRunConfig(
        cache_mode=CacheMode.ENABLED, # CacheMode.BYPASS(不使用缓存) CacheMode.ENABLED(使用缓存)
        wait_for_timeout=3000,# 等待超时时间(毫秒)
        # extraction_strategy=JsonCssExtractionStrategy({
        #     "name":'hot search', # 提取的数据的名字
        #     "baseSelector":".hotsearch-item", # 提取的数据的css选择器
        #     'fields':[
        #         {'name':'title','selector':'.title-content-title','type':'text'},# 标题
        #         {'name':'url','selector':'.title-content','type':'attribute','attribute':'href'},# 链接
        #     ],
        # })
        extraction_strategy=JsonCssExtractionStrategy(strategy)
    )
    # 第三段：
    async with AsyncWebCrawler(config=browser_config) as crawler:
        res = await crawler.arun(url=url,config=crawler_run_config)
        print(res.extracted_content) # 返回的json数组
        data=json.loads(res.extracted_content) # 数组
        # 保存csv文件
        df=pd.DataFrame(data)
        df.to_csv('guazi.csv',index=False,encoding='utf-8-sig')
# 第四段：
if __name__ == '__main__':
    asyncio.run(simple_demo())