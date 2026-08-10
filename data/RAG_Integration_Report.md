# 多轮对话 RAG (检索增强生成) 架构集成调研报告

## 1. 核心问题定义

在标准的多轮对话中，上下文通常以 `[System_Msg, User_Msg_1, Assistant_Msg_1, User_Msg_2, ...]` 的形式直接拼接。

引入 RAG 后，核心挑战在于：**检索到的知识片段（Context）应该插入到 Prompt 的哪个位置，以及这些 Context 在后续对话中如何处理？**

## 2. 主流 RAG 框架的处理模式

经过对 LangChain, LlamaIndex 以及工业界常见实践的调研，目前主流的做法如下：

### 2.1 上下文注入位置 (Context Placement)

**结论：** 最主流的做法是将检索到的 Context 放到 **当前轮次的 User Message** 中，或者在 User Message 之前紧邻的一个独立 block 中。

*   **做法**：
    构造一个 Prompt Template，例如：
    ```text
    根据以下参考资料回答用户的问题。
    参考资料：
    {context}
    
    用户问题：
    {question}
    ```
    将这个组合好的文本作为该轮的 `User Input` 发送给模型。

*   **为什么不建议放 System Prompt？**
    1.  **注意力衰减**：对于长上下文模型，位于中间或底部的 User Prompt 往往比顶部的 System Prompt 受到更强的注意力 (Recency Bias)。
    2.  **语义隔离**：System Prompt 通常用于定义"人设"和"安全边界"（如"你是一个专业的助手"），频繁修改 System Prompt 会破坏这种定义的稳定性。
    3.  **缓存友好性**：许多推理引擎（如 vLLM）对前缀（System Prompt）有缓存优化。如果每一轮都改 System Prompt，会导致缓存频繁失效。

### 2.2 历史上下文保留策略 (History Management)

**关键问题：** 下一轮对话时，上一轮检索到的 RAG 信息是否还保留？

**结论：** **不保留（Transient Context / 瞬时上下文）。**

在工业界标准实践（如 LangChain 的 `ConversationalRetrievalChain`）中，对话历史记录（Memory）和发送给大模型的 Prompt 是分离的。

1.  **第 N 轮对话流程**：
    *   **检索**：根据用户问题 Q1，检索到 Context C1。
    *   **生成**：构建 Prompt `[History, Context: C1, User: Q1]` -> 模型生成 Answer A1。
    *   **存储历史**：在对话历史数据库（如 Redis, SQL）中，只存储 `(User: Q1, Assistant: A1)`。**Context C1 通常被丢弃**。

2.  **第 N+1 轮对话流程**：
    *   **历史回溯**：读取历史 `(Q1, A1)`。
    *   **查询重写 (Query Rewriting)**：用户提出新问题 Q2（例如"它的价格是多少？"）。由于 Q2 包含指代词"它"，不能直接检索。
    *   **独立模型调用**：使用一个小 Prompt，将 `[History, Q2]` 发给 LLM，要求改写成独立问题 Q2'（例如"iPhone 15 的价格是多少？"）。
    *   **新检索**：根据 Q2' 检索新的 Context C2。
    *   **生成**：构建 Prompt `[History, Context: C2, User: Q2]` -> 模型生成 Answer A2。

**原因分析**：
*   **节省 Token**：如果每一轮都把几千字的 Context 塞入历史记录，两三轮后 Context Window 就会爆炸。
*   **减少噪音**：上一轮的参考资料可能与这一轮的问题无关，保留下来会干扰模型对新问题的判断。
*   **隐式记忆**：上一轮的重要信息已经通过 A1（Assistant 的回答）内化到了历史记录中。

---

## 3. 主流框架实现细节

### 3.1 LangChain
LangChain 是 RAG 的事实标准，其核心组件 `create_retrieval_chain` 和 `create_history_aware_retriever` 完美体现了上述逻辑。

*   **Workflow**:
    1.  **History Aware Retriever**: 接收 `chat_history` 和 `user_input`。如果 `chat_history` 不为空，先调用 LLM 生成一个 `search_query`（独立问题）。
    2.  **Retrieval**: 使用 `search_query` 去向量库检索 `docs`。
    3.  **Combine Docs Chain**: 将 `docs` 填充进 `context` 变量，结合 `chat_history` 和 `user_input` 发送给 LLM 生成最终回答。
*   **Memory**: 默认的 `ConversationBufferMemory` 只存储 User 的原始输入和 AI 的最终输出。

### 3.2 LlamaIndex
LlamaIndex 的 `ChatEngine` (Context Mode) 逻辑类似：

*   **System Prompt**: 可以定义固定的 System Msg。
*   **Context Template**: 检索到的 Nodes 被格式化为字符串，通常插入在 System Msg 之后，或者 User Query 之前。
*   **Memory**: 同样维护简洁的 User/AI 消息对。

### 3.3 OpenAI Assistants API
OpenAI 官方的 Assistants API 将这一过程黑盒化：

*   用户只需将文件上传至 `Vector Store`。
*   创建 `Run` 时，OpenAI 自动决定是否检索。
*   如果检索，它会自动将检索内容作为 `context` 注入到当前 `Run` 的上下文中。
*   **Thread**（对话历史）中并不直接显示检索到的海量原文，只显示用户的 Message 和 Assistant 的 Message（可能带有引用注解）。这证实了"瞬时上下文"的思路。

---

## 4. 总结建议

针对您的开发场景，建议采用以下架构：

| 组件 | 策略 |
| :--- | :--- |
| **System Prompt** | **保持静态**。仅包含角色设定、风格指南、安全限制。例如："你是一个乐于助人的AI助手..." |
| **Prompt 组装** | **[System] + [Chat History] + [Context Block] + [Current User Question]** |
| **检索信息 (Context)** | **放入当前轮 User Prompt**。使用明确的分隔符，如 `### Context ###`。 |
| **历史记录 (Memory)** | **只存问答对 (Q&A)**。不要存 Context。 |
| **多轮关键技术** | **Query Rewriting (问题改写)**。在检索前，必须先用 LLM 基于历史记录将当前模糊的用户问题（"它多少钱"）改写为完整问题（"xxx产品多少钱"）。 |

### 示例 Prompt 结构 (最后一轮)

```text
System: 你是 WechatArticleBot，负责根据提供的公众号文章回答问题。

(History 自动由框架插入)
User: 帮我找找关于 AI Agent 的文章。
Assistant: 好的，我找到了以下关于 AI Agent 的文章... (摘要)

User (Current Turn):
请根据以下背景信息回答问题。如果信息不足，请告知。

### 背景信息 ###
(这里插入 RAG 检索到的几段 chunk)
......
### 背景信息结束 ###

### 用户问题 ###
那其中提到的 Reflexion 架构是什么？
```
