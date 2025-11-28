from datetime import datetime

from litestar import post

from models.common import FlowRunResponse
from modules.agui_pozo_flow_v01 import classifier, extractor, postprocess, validate


@post("/api/agui/pozo/flow/v1/run")
async def run_agui_pozo_flow(payload: dict[str, str]) -> FlowRunResponse:
    """
    Laboratory endpoint for AG-UI Pozo Flow v01.
    The pipeline is intentionally explicit to map UI -> Classifier -> Extractor -> Postprocess -> Validator -> UI.
    """
    text = payload.get("text", "")
    intent = classifier.classify_intent(text)
    raw_extracted = extractor.extract_operation(text, intent.get("intent", "unknown"))
    normalized_operation = postprocess.apply_business_rules(raw_extracted)
    validation_errors = validate.validate_operation(normalized_operation)

    meta = {
        "request_id": "demo-req-001",
        "timestamp": datetime.utcnow().isoformat(),
    }

    return FlowRunResponse(
        raw_input=text,
        intent=intent,
        raw_extracted=raw_extracted,
        normalized_operation=normalized_operation,
        validation_errors=validation_errors,
        meta=meta,
    )
