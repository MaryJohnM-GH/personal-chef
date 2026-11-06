from guardrails import injection_score, on_topic, redact_pii

tests = [
    "Find me a recipe online using chicken, rice and broccoli",
    "I have chicken, rice and broccoli",
    "At what temperature is chicken safely cooked?",
]
for t in tests:
    cleaned = redact_pii(t)
    print(repr(t))
    print("  injection score:", injection_score(cleaned))
    print("  on topic:", on_topic(cleaned))