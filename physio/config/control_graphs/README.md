# PhysIO 控制图（PIO-M4；DYN-2 图动态层）
#
# 图源文件在此目录，经 tools/sign_graph.py 签名 + digest 冻结后下发固件。
# 算子集封闭（V1 候选，Q-PIO-09）：
#   limit / scale / filter / smooth / state_machine / compare / mux / delay / estop_hook
# 固件端绝不生成或修改图；未签名或 digest 不符一律拒载。
#
# 格式草案（待 ADR-PIO-0004）：
#   version, graph_id, nodes[{id, op, params(带范围)}], edges[{from, to}], safety{fallback_on_error}
