import sys
import os

spec_file = "KeepAlive.spec"

# 读取当前内容
with open(spec_file, "r", encoding="utf-8") as f:
    content = f.read()

# 修改第5行：将 src\\keepalive.py 改为 src\\keepalive.py
old_content = "    ['src\\\\keepalive.py'],"
new_content = "    ['src\\\\keepalive.py'],"

content = content.replace(old_content, new_content)

# 写回修改
with open(spec_file, "w", encoding="utf-8") as f:
    f.write(content)

print(f"✅ KeepAlive.spec 已更新：第5行已修改为 src\\\\keepalive.py")
