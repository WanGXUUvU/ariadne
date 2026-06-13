## Python基础操作

Split 把str转换成list ()里面放按照什么划分

join 把list转换成str ",".join(list)就是用,拼接起来

strip 是把字符串清理。lstrip只去除左边 rstrion只去除右边   

.lower()是。.upper是大写。.title是首字母大写 可以链式调用.strip().lower() 元字符串都不会变

- Tuple  和list的区别就是不可变 然后用()
- Set  不能重复的list 无索引 x in set速度极快  以及一些 交并补 set的pop顺序不固定 随机删除一个
- dict  for k，v  in dict.items 

## Agent

构建一次run上下文

构建runcontext：

1.State：由数据库取出 判断是否压缩返回最终结果

2.adapter 由session_id构建出

3.agent_profile 根据sessio_type来返回最终的agent类型 并在构建system_prompt替换掉原来的

.workspace_path由sessio_id查出来

5.sessio_type同上



### request和response



request Hearder:

~~~json
{
  "model":"my_model_name",
  "message":[
    {
      "role":"system",
      "content":"",
    },
    {
      "role":"user",
      "content":""
    },
    {
      "role":"assistant",
      "content":null,
      "tool_calls":[
        {
          "id":"tool_call_id_001",
          "type":"function",
          "function":{
            "name":"get_weather",
            "arguments":{city:"beijing"}
          }
        }
      ]
    },
    {
      "role":"tool",
      "tool_call_id":"tool_call_id_001",
      "content":"今天天气晴朗",
    }
  ],
  "stream":true,
  "tools":[
    {
      "type":"function",
      "function":{
        "name":"get_weathaer",
        "description":"用来查询用户指定的天气",
        "parameters":{
          "type":"object",
          "properties":{
            "city":{
              "type":"string",
              "description":"用户要查询的天气名称",
            },
            "data":{
              "type":"string",
              "description":"用户要查询的具体日期",
            },
          },
          "required":{"city","data"},
        }
      }
    }
  ],
  "tool_chocies":auto,
}
~~~

~~~markdown
一次大模型请求 Request
│
├── model
│   ├── 类型：string
│   ├── 示例："your-model-name"
│   └── 含义：指定本次调用使用哪个模型
│
├── messages
│   ├── 类型：list
│   ├── 含义：发送给模型的完整对话上下文
│   │
│   ├── [0] system 消息
│   │   ├── role = "system"
│   │   ├── content = 系统提示词
│   │   └── 含义：规定模型身份、行为规则、工具使用原则
│   │
│   ├── [1] user 消息
│   │   ├── role = "user"
│   │   ├── content = 用户的问题
│   │   └── 含义：用户本轮输入
│   │
│   ├── [2] assistant 消息（模型要求调用工具时）
│   │   ├── role = "assistant"
│   │   ├── content = null 或少量文本
│   │   ├── tool_calls
│   │   │   ├── 类型：list
│   │   │   └── 含义：模型生成的一个或多个工具调用计划
│   │   │
│   │   │   └── [0] 一个工具调用
│   │   │       ├── id
│   │   │       │   ├── 示例："call_001"
│   │   │       │   └── 含义：这一次工具调用的唯一标识
│   │   │       │
│   │   │       ├── type = "function"
│   │   │       │   └── 含义：调用的是函数型工具
│   │   │       │
│   │   │       └── function
│   │   │           ├── name
│   │   │           │   └── 含义：要调用的工具名称
│   │   │           │
│   │   │           └── arguments
│   │   │               ├── 类型：JSON 字符串
│   │   │               ├── 示例："{\"city\":\"北京\"}"
│   │   │               └── 含义：模型为工具生成的实际参数
│   │   │
│   │   └── 含义：这不是最终回答，而是模型要求 Runtime 执行工具
│   │
│   └── [3] tool 消息（Runtime 执行工具后追加）
│       ├── role = "tool"
│       ├── tool_call_id = "call_001"
│       │   └── 含义：关联上一条 assistant.tool_calls 中的 id
│       ├── content
│       │   ├── 类型：通常是字符串
│       │   ├── 示例："{\"weather\":\"晴\",\"temperature\":28}"
│       │   └── 含义：工具真实执行后返回的结果
│       └── 含义：把工具结果交回模型继续生成
│
├── tools
│   ├── 类型：list
│   ├── 含义：本次请求允许模型使用的工具说明
│   │
│   └── [0] 一个工具定义
│       │
│       ├── type = "function"
│       │   └── 含义：这是函数型工具
│       │
│       └── function
│           │
│           ├── name
│           │   ├── 示例："get_weather"
│           │   └── 含义：工具名称
│           │
│           ├── description
│           │   └── 含义：说明工具做什么，帮助模型判断是否调用
│           │
│           └── parameters
│               ├── 含义：工具参数的 JSON Schema
│               │
│               ├── type = "object"
│               │   └── 含义：所有参数组成一个 JSON 对象
│               │
│               ├── properties
│               │   ├── 含义：定义允许传入的每一个参数
│               │   │
│               │   └── city
│               │       ├── type = "string"
│               │       │   └── 含义：city 必须是字符串
│               │       ├── description
│               │       │   └── 含义：解释 city 参数用途
│               │       ├── minLength
│               │       │   └── 含义：字符串最短长度
│               │       └── maxLength
│               │           └── 含义：字符串最长长度
│               │
│               ├── required
│               │   ├── 示例：["city"]
│               │   └── 含义：列出必须提供的参数
│               │
│               └── additionalProperties = false
│                   └── 含义：禁止生成 properties 中未定义的额外参数
│
├── tool_choice
│   ├── 示例："auto"
│   └── 含义：控制模型如何选择工具
│              auto：模型自行判断
│              none：禁止调用工具
│              指定工具：强制调用某个工具
│
├── temperature
│   ├── 示例：0.2
│   └── 含义：控制输出随机性
│
├── stream
│   ├── 示例：true
│   └── 含义：是否使用流式响应
│
└── stream_options
    └── include_usage = true
        └── 含义：在流结束前额外返回 token 使用量
~~~

1.拼接一次run的上下文

-----ctx 返回的是runcontext

需要的属性agent_input 

- State:agentstate()从数据库读取 主要是list[Chatmessages] step 
  - 先从session_id获取
  - 实例化一个compactor
  - 把这个compactor传入一个压缩类 进行自动压缩 得到最新的state

- Workspace_path 通过绑定的session_id找到
- adpater 通过session_id获取的 
  - 通过session_id得到去查模型配置表 得到base_url 和 model
  - 构建一个通讯器 放着 下层可以直接调用这个adapter 来和模型通讯
- session type coding还是助手
- approval。审批 通过session id获得
- agent_profile:最终用到的agent的配置文件 包含了 更新过后的系统提示词 （skill的概述 agent.md user.md ） 以及可以使用的工具列表
  - 根据effective agent name  拿到他的system prompt
  - 根据workspace path得到当前目录下的agent.md等文件的description
  - 根据agent_input是否传入skill选择加载skill的content 默认加入content的概要
- effective agent name:本轮实际用的agent

2.observer:构建一个工具trace类 ToolTracer 给后面具体执行工具时使用 包含三个方法on_tool_start，on_tool_end，on_tool_approval

- 需要的属性
  - db 统一service的db
  - _run_store:run过程中的类型 包含了几个方法
    - 保存 run record。
    - 保存 run event record
    - 创建toolcallrecord
    - 更新toolcallruncord
  - approval类
  - 这次run的id
  - 这次的agent input

- on_tool_start:工具开始之前
  - 调用 _run_store的创建toolcall record 方法
    - 拿到run id tool name 以及实际调用房传入toolcall id 和 input json status 默认时running
- on_tool_end:工具结束之后
  - 调用finish tool 方法更新toolcall record 根据实际情况更新tool的状态status 并且填入result
- on_tool_approval:需要审批
  - 调用approval类的create方法创建一条审批记录
    - 需要 run id toolname  toolcall id   arguments 方便恢复的时候使用
    - batch_id：一次循环返回的一批需要审批的工具
    - savedmessages 保存临时信息具体执行结果
    - event_index用于保存时间记录顺序 恢复的时候不中断

3.搭建agent_runner 传入ctx上下文 返回一个AgentRunner 正式跑循环的

- state: ctx里面的
- agent_profile:ctx里面的agent_profile 也就是实际的使用的并且更新提示词的agent
- allow tool names ctx中的最终使用的agent中的
- model_adapter ctx中构建的和大模型通讯器 拿到通讯器后
- **tool_registry**工具注册中心 这次搭建的发动机里面真正的新增的
  - 返回一个tool registry类 包含了默认注册中心 以及三个动态注册
- approval_policy 审批政策

4.开始跑流式循环 RunSSEBridge，返回一个个frame 展示到前端

- 需要把上面的ctx agent_runner observer agent_input 传进去
- 以及最开始生成的 run_Id持久化方法persist
- 进入之后RunSSEBridge之后stream
  - 第一步yield出去一个开始frame
  - 构建run执行的生命周期 将run所有需要的物料放进去 返回一个Runlifecyle 类
    - 包含了 ctx上下文、agent_input、agent_runner、persist、run_id、observer的三个方法
    - skip user input只有resume的时候才需要
    - event_index默认是0 但是resume需要传入
    - intial_events 默认是空的只有执行resume 才会吧工具执行结果放进去
    - append_events 默认false 新建runrecord 加写入event。resume时候是在已经有的run 追加event
    - update_session_snapshot 控制更新session的state 给子agent用的防止污染主会话state_json
  - 根据构建的runlifecycle类 开始执行它的iterate()方法 也就是一步步产生item 然后判断item的类型包装成SSeSTREAM不断yield出去 
    - 包含这几种类型 正常文本、thinking内容、agentevent 可以是tool call。toolresult thinking
    - 但是最终如果是yield出来的finalresultitem 他会包含一个RunLifeCycleResult 
      - RunLifeCycleResult包含了status、部分回复、events、usage、state
    - 如果他的status事暂停 那么就yield出去一个暂停frame
    - 否则就yield 出去一个end

5.进入Runlifecycle实际执行 iterate 返回RunLifecycleItem包括了上层所需要的四种item

- 新准备好三个列表 首先是str的 然后是thinking的。然后是 agent event
- 构建一个刷新thinking列表的 如果thinking列表不是空的 几句返回一个agent_event item 保存为event 同时yield出去
- 然后开始真正的循环async_stream_run 用的是物料里的a gent_runner发动机 然后传入物料中各种需要
  - 传入agent_input、三个工具tracer、工作区、是否跳过userinput（用于恢复）event_index 默认是0 恢复才追加 run id workspacepath
  - 返回 RunEvent 或者是str 或者是ModelStreamEvent
  - 如果返回的是str 就先保存在str列表 然后yieldTextDeltaItem
  - 如果返回的是agentevent 调用thinking刷新列表 thinking 然后就落库 并yield出去 再把agentevent yield 出去并保存到event
  - 如果返回的是 modelstream 证明是下层传出来的 thinking 片段 一边yield出去一边保存到thinking列表里
  - 最后补充一次刷新thinking列表
  - 执行完这次循环就是落库环节 
    - 首先判断run status 如果event的types里面包含approval_required那么就是暂停否则就是完成
    - 并且把status和 events 以及最终回复 调用finalize_run方法落库
    - 并且yiled出去一个status 供外层接受
    - 如果try失败捕获取消异常 先刷新一次thinking status=cancelled落库
    - 如果失败 同样刷新一次thinking  status=failed 落库

6.开始真正的执行agentrunner里面的循环，在上面构建agentrunner时 已经有了足够的物料

默认在构建agentrunner时已经准备好的物料：

- state 经过压缩后的state
- approval_policy 审批策略
- 工具注册中心
- agent_profile
- Model_adapter 选择用哪种通讯器通讯
- session type

agentrunner包含了三种方法：execute 非流式 stream_run同步流式 async_stream_run异步流式

- 执行async_stream_run循环
  - 需要的额外参数 在runlifecycle 物料中获取
    - Tool tracer 
    - 是否跳过用户输入 主要是resume
    - run_input 一次run的请求体
    - event_index 用于resume 之后恢复后保持event 的 index 默认0
    - run_id
    - workspace path 作为透传 只有在执行工具时生效
  - 先判断是否跳过用户输入 如果不跳过 就是state 先增一条 role =user content = run_input.user_input
  - 正式循环进入循环
    - 拿到agent_profile、state、tool registry 构建request
      - 构建message。role=system content=agent_profile.system_prompt
      - 构建tools 把agent_profile中的tools 给到toolregitsty 构建出工具说明书
    - 把request交给adpater 去和大模型联络并返回 用模型返回的response包装成 stream chunk返回
    - 我们用这些chunk的type对比包装成
