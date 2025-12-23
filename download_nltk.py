import nltk
import ssl

# 尝试解决SSL证书验证问题，这在某些网络环境下是必需的
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

print("开始下载 NLTK 的 'punkt' 模型...")
print("这个过程可能需要一些时间，取决于您的网络状况。")
print("如果一次不成功，请多尝试运行几次这个脚本。")

try:
    # 'punkt' 是分词模型，'averaged_perceptron_tagger' 用于词性标注，
    # 有时也会被依赖，我们一起下载以防万一。
    nltk.download('punkt')
    nltk.download('averaged_perceptron_tagger') 
    print("\n下载成功！所需NLTK资源已准备就绪。")
    print("您现在可以重新运行 'build_database.py' 了。")
except Exception as e:
    print(f"\n下载过程中发生错误：{e}")
    print("请检查您的网络连接、防火墙或代理设置，然后重试。")
    print("如果持续失败，请尝试方法二（手动离线安装）。")