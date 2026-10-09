import pandas as pd
import numpy as np

# 1.准备包含缺失值的DataFrame学员打卡数据
data = {
    "学员姓名": ["小明", "小红", "小刚", "小丽"],
    "学习时长": [120, np.nan, 90, np.nan]
}
df = pd.DataFrame(data)
print("原始数据：")
print(df)

# 方式一：dropna() 删除存在缺失值的行
df_drop = df.dropna()
print("\n删除缺失行后：")
print(df_drop)

# 方式二：fillna(0) 使用0填充缺失学习时长
df_fill = df.fillna({"学习时长": 0})
print("\n用0填充缺失值后：")
print(df_fill)