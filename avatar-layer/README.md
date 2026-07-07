# Thebenpaul Avatar Layer

Standalone Phase 1 avatar interaction layer for assessment playback. It is dependency-free and uses Python stdlib HTTP serving plus a static browser shell.

The service is advisory only. It transforms governed product-layer and agents-layer assessment payloads into spoken summaries, display summaries, transcript metadata, next actions, and role-filtered evidence references. It does not mutate product, agent, or data-layer records.

## Run

```bash
cd /Users/Shared/code/paul/ihk-theben-challenge-2026/avatar-layer
python3 -B app/app.py --host 127.0.0.1 --port 8095
```

Open `http://127.0.0.1:8095/`.

## Test

```bash
cd /Users/Shared/code/paul/ihk-theben-challenge-2026/avatar-layerul-avatar-layer grep -n "Confidence describes" /app/app/app.py
python3 -B -m unittest discover -s tests -v
```

## API

`GET /health`

Returns service health and timestamp.

`GET /api/config`

Returns runtime, avatar profile, assessment mode, and safe client policy configuration.

`POST /api/avatar/assess`

Alias: `POST /api/assess`

Accepts:

```json
{
  "role": "viewer",
  "product_id": "THB-001",
  "agent_ids": ["expert-dpp-readiness"],
  "assessment_mode": "dpp",
  "assessment": {
    "readiness": {"status": "review_required", "score": 72},
    "findings": []
  }
}
```

Returns:

- `spoken_summary`
- `display_summary`
- `assessment_status`
- `severity`
- `confidence`
- `evidence_refs`
- `restricted_refs_hidden`
- `missing_evidence`
- `human_review_required`
- `next_actions`
- `agent_versions`
- `transcript`
- `session`

## Integration Notes

Product-layer Assess should pass `product_id`, current viewer role, requested `assessment_mode`, optional `agent_ids`, and the structured assessment payload returned by agents-layer. The avatar-layer can also accept a product-id-only request, but then returns a `missing_context` contract until governed findings are supplied.

Evidence text and references are filtered by `config/speech_policies.json`. Viewer and reviewer roles receive redacted restricted evidence markers. Steward and admin roles can inspect restricted evidence reference text in the JSON response, but spoken summaries still avoid restricted detail by policy.

Browser speech uses the Web Speech API when available. Mute, reduced-motion, and text-only controls are first-class static UI states and require no build tooling.
