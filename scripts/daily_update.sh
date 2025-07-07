# 注：调用shell时不要开科学上网工具（亲测在windows系统git bash中运行shell导致request失败）
echo "爬取公众号最新文章ing"
cd "D:\learning\python\WeChatOA_Aggregation"
D:\\anaconda\\envs\\torch20\\python main.py

if [ $? -ne 0 ]; then
    echo "请求次数过多，或session及token过期，请查看异常获取详细信息"
    exit 1
else
    echo "爬取成功"
fi

echo "上传md文件中ing"
SOURCE_PATH1="D:\learning\python\WeChatOA_Aggregation\data\微信公众号聚合平台_按时间区分.md"
SOURCE_PATH2="D:\learning\python\WeChatOA_Aggregation\data\微信公众号聚合平台_按公众号区分.md"
TARGET_PATH="D:\learning\zejun'blog\Hexo\source\_posts"

# 检查目标路径是否存在，如果不存在，则打印错误并退出
if test -d "$TARGET_PATH"; then
    cp $SOURCE_PATH1 $TARGET_PATH
    cp $SOURCE_PATH2 $TARGET_PATH
else
    echo "目标路径不存在: $TARGET_PATH"
    exit 1
fi

cd "D:\learning\zejun'blog\Hexo"
hexo g -d