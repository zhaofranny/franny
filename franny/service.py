"""The same import/analyze/generate/save path for UI and CLI tests."""
import json
from .errors import explain_error
from .generation import generate

def create_and_save(store, topic, audience, insights, *, provider, demo=False, text_only=True, direction=None, client=None):
    lease=store.reserve_generation(provider) if not demo else None
    try:
        payload=generate(topic,audience,insights,provider=provider,demo=demo,text_only=text_only,direction=direction,client=client)
        # Do not serialize provider config, credentials, raw API objects or errors.
        draft_id=store.save_draft(json.dumps(payload,ensure_ascii=False))
        return draft_id,payload
    except Exception as exc:
        report=explain_error(exc,provider)
        if not demo and report.get('retry_after_seconds'):
            store.set_cooldown(provider,report['retry_after_seconds'])
        raise
    finally:
        if lease:
            store.release_generation(provider,lease)
