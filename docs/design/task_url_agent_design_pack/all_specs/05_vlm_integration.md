# 05 — Local VLM Integration

## Purpose

Local VLMs should help the agent understand ambiguous rendered pages and screenshots. The VLM should guide browser actions, not replace deterministic extraction.

The user may run local VLMs on their own system. The implementation must be pluggable and should not hardcode a single provider.

## When to Use VLM

Use VLM only when deterministic methods do not give enough confidence, such as:

- page has visible download controls but DOM labels are unclear,
- site has complex menus/dropdowns,
- page is image-heavy,
- relevant content is visible in screenshot but not easy to extract from HTML,
- deciding which button/tab to click,
- distinguishing useful disclosure pages from irrelevant pages.

## VLM Inputs

Send structured context:

```json
{
  "objective": "Find mutual fund portfolio disclosure, factsheet, NAV, or scheme data downloads.",
  "current_url": "...",
  "page_title": "...",
  "visible_text_excerpt": "...",
  "links": [
    {"text": "Portfolio Disclosure", "href": "..."}
  ],
  "buttons": ["Download", "Search"],
  "forms": ["AMC", "Scheme", "Date"],
  "screenshot_path": "..."
}
```

## VLM Output

The VLM must return structured JSON:

```json
{
  "page_relevance": "high|medium|low|irrelevant|unknown",
  "dataset_hints": ["portfolio_disclosure", "factsheet"],
  "recommended_action": "click|select|download|extract_links|go_back|skip|unknown",
  "target_text": "Portfolio Disclosure",
  "target_selector_hint": null,
  "form_values": {},
  "avoid_targets": ["Careers", "Contact Us"],
  "reason": "The screenshot shows a monthly portfolio disclosure download section.",
  "confidence": 0.82
}
```

Do not accept freeform prose as the control signal. If the VLM output cannot be parsed, log the failure and continue deterministically.

## Validation of VLM Suggestions

Before acting, validate:

- target text exists in rendered DOM or accessibility tree,
- suggested action is in allowed action list,
- target does not match blocked action rules,
- confidence meets configured threshold.

If validation fails, store VLM decision but do not act blindly.

## VLM Provider Interface

Create an interface like:

```python
class VLMClient:
    def analyze_page(self, payload: PageAnalysisPayload) -> PageAnalysisDecision:
        ...
```

Possible backends:

- disabled/null backend,
- local HTTP endpoint,
- Ollama-compatible endpoint,
- OpenAI-compatible local server,
- custom command-line adapter.

Default should be disabled unless `--use-vlm true`.

## Stored VLM Artifacts

Store:

- screenshot path,
- prompt/context JSON,
- raw response,
- parsed response,
- action taken,
- success/failure.
