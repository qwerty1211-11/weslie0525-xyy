import json
import jsonpath
data = {
   "products": [
       {"name": "手机", "price": 1000},
       {"name": "电脑", "price": 5000}
   ]
}
result = jsonpath.jsonpath(data, '$.products[*].name')
print(result)

import requests
import time


def fetch_data(url, params, max_retry=3):
    for retry in range(max_retry):
        try:
            response = requests.get(url, params=params, timeout=10)
            # 判断状态码是否为200
            if response.status_code == 200:
                print("采集成功")
                return response.json()
            else:
                print(f"状态码异常：{response.status_code}，准备重试")
        except Exception as e:
            print(f"请求发生异常：{str(e)}，准备重试")
        time.sleep(1)

    print(f"已经达到最大重试次数{max_retry}，采集失败")
    return None
if __name__ == "__main__":
    api_url = "https://api.example.com/search"
    get_params = {
        "keyword": "手机",
        "page": 1,
        "size": 10
    }
    result = fetch_data(api_url, get_params, max_retry=3)
    print(result)

