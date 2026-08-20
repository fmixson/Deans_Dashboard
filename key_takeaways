"""
key_takeaways.py
------------------
Auto-generates a short, plain-English summary of the current data —
the kind of thing a dean would want to read FIRST, before digging
into any tables. Uses the same Claude API call as the chat, just
with a different prompt (asking for a summary instead of answering
a question).
"""

import anthropic


def generate_takeaways(api_key, context):
    """
    Asks Claude for a short bulleted summary instead of answering a
    specific question. Reuses the exact same context text the chat
    feature builds — one consistent source of truth for what Claude
    knows, whether it's answering a question or summarizing.
    """
    client = anthropic.Anthropic(api_key=api_key)

    prompt = (
        "Based on the enrollment data below, write a short \"Key Takeaways\" "
        "summary for a dean — 3 to 5 bullet points, no more. Lead with the "
        "single most important thing (e.g. the biggest problem area or the "
        "most notable change from last week). Use specific numbers. Keep each "
        "bullet to one sentence. Do not repeat raw numbers already obvious from "
        "a headline count (like just restating 'total sections') — focus on "
        "what a dean should actually DO or PAY ATTENTION TO.\n\n"
        f"{context}"
    )

    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )

    return response.content[0].text
