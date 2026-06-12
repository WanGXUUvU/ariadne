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

1拼接一次run的上下文

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

2.observer:构建一个工具观测类 给后面具体执行工具时使用 包含三个方法on_tool_start，on_tool_end，on_tool_approval

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
- 以及runId最开始生成的 持久化方法persist
- 进入之后RunSSEBridge之后 首先要做的就是
