# 系统接入指南

## 接入方式
BKFlow 提供了两种不同的接入方式，您可以根据自己的需求选择合适的方式进行接入。

### 1. 接入系统嵌入 BKFlow 画布
在这种场景下，接入系统将 BKFlow 的画布嵌入到自己的应用程序中，以便接入系统的用户可以直观地创建、编辑和管理流程。

通过在 BKFlow 注册对应的空间，接入系统可以获取该空间下资源的管理权限，并通过 API 调用来管理这些资源。

通过嵌入 BKFlow 的画布，接入系统的用户无需感知到 BKFlow 的存在，但是其编辑和查看流程和任务的操作实际上是在 BKFlow 中进行的。接入系统通过替用户申请 Token 的方式来授予用户直接在画布中查看、编辑流程以及执行、操作任务的权限，用户带着 Token 和对应资源 id 访问 BKFlow 时，即可直接访问到对应的资源并进行操作。

以下是这种场景下用户、接入系统和 BKFlow 之间的交互流程图：
``` mermaid
sequenceDiagram 
    actor user1
    participant a as Access System
    participant b as BKFlow
    
    a->>+b: register space
    b-->>-a: space_id
    Note over a,b: register space 
    
    user1->>+a: create template/task
    a->>+b: create template/task
    b-->>-a: template/task id
    a->>+b: fetch canvas token
    b-->>-a: token
    a-->>-user1: template/task id + token
    user1->>+b: open canvas to visit template/task
    b-->>-user1: canvas
    Note over user1, b: create template/task and open canvas
```

### 2. 接入系统实现画布
在这种场景下，接入系统需要自己实现画布，并通过调用 BKFlow 的 API 来实现流程和任务的管理和执行。

在这种场景下，接入系统需要理解 BKFlow 的流程和任务协议 pipeline_tree，并在接口交互中将 pipeline_tree 作为参数传递给 BKFlow。BKFlow 会根据 pipeline_tree 的定义来执行流程和任务。

以下是接入系统实现了自己的画布和流程管理，只依赖 BKFlow 进行任务执行的场景下，用户、接入系统和 BKFlow 之间的交互流程图：
``` mermaid
sequenceDiagram 
    actor user1
    participant a as Access System
    participant b as BKFlow
    
    a->>+b: register space
    b-->>-a: space_id
    Note over a,b: register space 
    
    user1->>+a: create template
    a-->>-user1: template with canvas
    Note over user1, a: create template and open canvas
    
    user1->>+a: create task with pipeline_tree
    a->>+b: create task
    b-->>-a: task data
    a-->>-user1: task with canvas
    Note over user1, b: create task and open canvas
```
