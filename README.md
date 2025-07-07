# WeChatOA_Aggregation

微信公众号聚合平台，获取多个公众号的博文进行筛选、过滤，使用户更方便的读取公众号上的所有文章

![blog_preview.png](output/assets/blog_preview.png)

## 📢 项目重构说明

**本项目已完成标准化重构！** 新结构更加模块化、专业化，符合开源项目标准。

- 📁 **新目录结构**: 采用标准Python包结构
- ⚙️ **模块化设计**: 清晰的功能模块分离
- 🔧 **配置管理**: 统一的YAML配置文件
- 📦 **标准安装**: 支持pip安装和打包
- 🧪 **测试框架**: 完整的测试和开发工具支持

详情请查看 [📋 重构完成报告](重构完成报告.md) 和 [📖 重构设计文档](project_structure_redesign.md)

## 🚀 快速开始

### 安装依赖
```bash
pip install -r requirements.txt
```

### 配置项目
```bash
# 复制示例配置文件
cp config/config.example.yaml config/config.yaml

# 编辑配置文件，填入你的微信token和cookie
nano config/config.yaml
```

### 运行项目
```bash
# 使用新的模块化入口
python -m wechat_aggregator.main

# 或使用配置文件
python -m wechat_aggregator.main config/config.yaml
```


## 关于token和cookie
进入微信公众平台，扫码登录后在网页地址栏最后面就可以看到`token=xxxxxxxxx`，
此时按F12点Network监控网络请求，选中Fetch/XHR，刷新一下网页，随便点击一个请求就可以找到Cookie字段

目前支持token或cookie自动过期时，会自动打开浏览器，弹出公众号页面，用户扫码登录后自动获取token和cookie

## TODO
- [x] 根据标题筛选可能相似博文，再获取具体内容计算重复率去重，去除大量转载文章
- [ ] 使用向量编码模型对文章编码，去除重复文章，防止出现标题不同文章相同的问题
  - 长文本准确率较低
- [x] 使用minhash+LSH算法对文章编码，去除重复文章
  - 0.9阈值找到的528篇文章，检测准确率100%，召回率待测
- [x] 定期爬取，每天早上8:00爬。爬取当前早上6:00到昨天早上6:00的
  - 需要架设服务器，当前支持终端运行`daily_update.sh`文件获取最新文章，我直接上传到hexo博客上，可根据自己需求更改sh文件
- [x] cookie和token过期自动模拟登陆获取
- [x] 已读取的文章定期检测是否博文已删除
- [x] 爬取次数限制，记录最新爬取时间，若一天内爬取过跳过，反复执行直到爬取完成
- [x] github pages搭建个人博客，将公众号聚合平台部署上去（简易版）：https://zejuncao.github.io/
- [ ] 增加搜索功能，关键词粗召回，再向量重排
- [ ] 去除广告等无用博文
- [x] 请求频率限制时，切换代理ip
  - 想主打一个零成本，但免费的代理ip不稳定
  - 现在微信取消了请求次数限制，可一次爬取所有内容
- [x] 优化hexo网页显示或自己搭建一个博客(使用更好看一些的hexo主题)
- [x] 拆分单个博客，并显示封面
- [x] 支持站内搜索

## minHash实验记录
- 在 4005 条博文的测试集下做的实验记录
- 其中 minhash_0.9 代表 MinHashLSH 的阈值设置为 0.9

| 方法                | 检测重复个数 | 错误个数           |
|-------------------|--------|----------------|
| minhash_0.9       | 528    | 0              |
| minhash_0.8       | 699    | 24             |
| minhash_0.8+规则0.7 | 665    | 1 (文字很少，主体为图片) |

## 类似项目参考
- https://github.com/jooooock/wechat-article-exporter
- https://github.com/1061700625/WeChat_Article