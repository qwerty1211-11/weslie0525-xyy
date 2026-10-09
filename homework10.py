import json
import os
flish_name="record.json"
if os.path.exists(flish_name):
    with open(flish_name,"r",encoding="utf-8") as f:
        data = json.load(f)
        print(data)
else:
    dir={}
    dir={"goods":"水杯","price":29.9}
    with open(flish_name,"w",encoding="utf-8") as f:
        json.dump(dir, f, ensure_ascii=False)
