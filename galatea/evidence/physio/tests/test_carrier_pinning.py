"""env↔subject 载体串双侧一致性钉死（P06 禁 env import subject——钉死测试住 evidence 侧）。"""
from galatea.env.physio.bridge import CARRIER_INTERO_CONTENT_TYPE
from galatea.subject.sensorium.ingest import CARRIER_INTERO


def test_bridge_carrier_literal_matches_ingest_contract() -> None:
    """env 侧字面量与 ingest 合同逐字同源（漂移即双侧失配——fail-closed 前的钉死）。"""
    assert CARRIER_INTERO_CONTENT_TYPE == CARRIER_INTERO
