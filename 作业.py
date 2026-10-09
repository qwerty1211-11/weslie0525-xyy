fruir=['apple','orange','banana',"watermelon","grape","mangou"]
print(fruir[:3])
print(fruir[2:5])
print(fruir[4:6])
import os
content=["chapter1","chapter2","chapter3"]
for item in content:
    os.makedirs(item,exist_ok=True)
    print(item)
