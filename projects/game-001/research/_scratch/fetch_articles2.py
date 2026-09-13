# -*- coding: utf-8 -*-
import sys, io
sys.stdout.reconfigure(encoding="utf-8")
import net

URLS = [
    ("jingyan_quxian", "https://jingyan.baidu.com/article/a3a3f8110d95cbcca2eb8aba.html"),
    ("csdn_quxian", "https://blog.csdn.net/u013741272/article/details/158009634"),
    ("pconline_quxian", "https://g.pconline.com.cn/x/1657/16574075.html"),
    ("phpcn_speed", "https://www.php.cn/faq/3069669.html"),
]

for name, u in URLS:
    print("\n" + "#" * 74)
    print("### %s  %s" % (name, u))
    try:
        b = net.raw(u)
        t = net.text_of(b)
        # trim boilerplate
        print(t[:6500])
    except Exception as e:
        print("FAIL", type(e).__name__, e)
