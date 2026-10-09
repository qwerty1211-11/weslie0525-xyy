from hashlib import md5
md5_obj = md5()
md5_obj.update("a".encode("utf-8"))
print(md5_obj.hexdigest())
text="weslie"*1000000
md5_obj.update(text.encode("utf-8"))
print(md5_obj.hexdigest())
