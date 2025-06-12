def calculate_job_state(node_states):
    """计算Job状态
    规则：
    - 未执行：所有Node状态均为READY
    - 执行中：存在Node状态为RUNNING
    - 失败：存在节点状态为FAILED
    - 完成：所有节点完成
    """
    if not node_states:
        return "READY"

    # 检查是否存在FAILED节点
    if "FAILED" in node_states:
        return "FAILED"

    # 检查是否存在RUNNING节点
    if "RUNNING" in node_states:
        return "RUNNING"

    # 检查是否所有节点都是READY
    if all(state == "READY" for state in node_states):
        return "READY"

    # 检查是否所有节点都FINISHED
    if all(state == "FINISHED" for state in node_states):
        return "FINISHED"

    # 如果既有FINISHED又有READY，说明在执行中
    return "RUNNING"


def calculate_stage_state(job_states):
    """计算Stage状态
    规则：
    - 未执行：所有Job状态均为READY
    - 执行中：存在Job状态为RUNNING
    - 失败：存在Job状态为FAILED
    - 完成：所有Job完成
    """
    if not job_states:
        return "READY"

    # 检查是否存在FAILED的Job
    if "FAILED" in job_states:
        return "FAILED"

    # 检查是否存在RUNNING的Job
    if "RUNNING" in job_states:
        return "RUNNING"

    # 检查是否所有Job都是READY
    if all(state == "READY" for state in job_states):
        return "READY"

    # 检查是否所有Job都FINISHED
    if all(state == "FINISHED" for state in job_states):
        return "FINISHED"

    # 如果既有FINISHED又有READY，说明在执行中
    return "RUNNING"
