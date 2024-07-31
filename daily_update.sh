echo "爬取公众号最新文章ing"
D:\\anaconda\\envs\\transformers\\python D:\\learning\\python\\WeChatOA_Aggregation\\main.py
if [ $? -ne 0 ]; then
    echo "请求次数过多，请稍后再次请求"
    exit 1
fi

echo "上传md文件中ing"
SOURCE_PATH="D:\learning\python\WeChatOA_Aggregation\data\微信公众号聚合平台.md"
TARGET_PATH="D:\learning\zejun'blog\Hexo\source\_posts"

# 检查目标路径是否存在，如果不存在，则打印错误并退出
if test -d "$TARGET_PATH"; then
    cp $SOURCE_PATH $TARGET_PATH
else
    echo "目标路径不存在: $TARGET_PATH"
    exit 1
fi

cd "D:\learning\zejun'blog\Hexo"
hexo g -d