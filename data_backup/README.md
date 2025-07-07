# 微信公众号聚合平台数据文件说明

本目录包含了微信公众号聚合平台所需的各类数据文件。以下是各个文件的详细说明：

## 数据文件

### 基础配置文件
- `id_info.json` - 包含微信公众平台的基础配置信息，如token和cookie等认证信息
- `name2fakeid.json` - 存储公众号名称到其对应的fakeid映射关系，用于公众号文章的获取

### 文章数据文件
- `message_info.json` - 原始的公众号文章信息数据
- `message_detail_text.json` - 存储文章的详细内容文本
- `issues_message.json` - 记录文章处理过程中的问题和异常情况

### 去重相关文件
- `minhash_dict.pickle` - 使用MinHash算法生成的文章指纹数据，用于文章去重

### 展示相关文件
- `微信公众号聚合平台_按公众号区分.md` - 按照公众号分类整理的文章展示文件
- `微信公众号聚合平台_按时间区分.md` - 按照发布时间整理的文章展示文件

## 文件用途说明

1. 数据采集和认证：
   - 使用`id_info.json`中的认证信息进行API访问
   - 通过`name2fakeid.json`获取目标公众号的唯一标识

2. 文章处理流程：
   - 首先获取的原始数据存储在`message_info.json`
   - 文章详细内容保存在`message_detail_text.json`

3. 文章去重机制：
   - 使用MinHash算法生成文章指纹，存储在`minhash_dict.pickle`
   - 记录MinHash重复和已被删除的博文，存储在`issues_message`

4. 内容展示：
   - 分别通过按公众号和按时间两种方式组织文章，生成对应的md文件