"""
ai_assistant.py
----------------
Lets deans ask natural-language questions about the enrollment data
they're currently viewing. We DON'T give Claude access to the whole
database — instead, we build a compact text summary of exactly what's
on screen (the current division/department scope) and send that,
along with the question, to Claude's API.
"""

import anthropic


def build_context(scope_label, breakdown_display, modality_display,
                   critically_low_df, low_not_growing_df, section_count,
                   breakdown_label="DEPARTMENT BREAKDOWN"):
    """
    Turns the dataframes already being shown on screen into a plain
    text summary — this is what Claude actually "sees." Keeping it
    text (not raw dataframes) keeps the API call simple and cheap.

    breakdown_display / breakdown_label: this is DEPARTMENT breakdown
    on the drill-down page, or DIVISION breakdown on the landing
    page — same shape of table, just grouped differently, so one
    function handles both instead of writing it twice.
    """
    lines = [f"Enrollment data for: {scope_label}", f"Total sections: {section_count}", ""]

    lines.append(f"{breakdown_label}:")
    lines.append(breakdown_display.to_string(index=False))
    lines.append("")

    lines.append("MODALITY BREAKDOWN:")
    lines.append(modality_display.to_string(index=False))
    lines.append("")

    lines.append(f"CRITICALLY LOW SECTIONS ({len(critically_low_df)} total):")
    if len(critically_low_df) > 0:
        lines.append(critically_low_df.to_string(index=False))
    else:
        lines.append("None")
    lines.append("")

    lines.append(f"LOW & NOT GROWING SECTIONS ({len(low_not_growing_df)} total):")
    if len(low_not_growing_df) > 0:
        lines.append(low_not_growing_df.to_string(index=False))
    else:
        lines.append("None")

    return "\n".join(lines)


def ask_claude(api_key, context, question, conversation_history):
    """
    Sends the question to Claude, along with the data context and
    any prior turns in this chat (so follow-up questions work).

    conversation_history: list of {"role": "user"/"assistant", "content": str}
    from previous turns in THIS chat session — lets Claude remember
    what was already asked.
    """
    client = anthropic.Anthropic(api_key=api_key)

    system_prompt = (
        "You are a helpful assistant for a college dean, answering questions "
        "about their division's enrollment data. Here is the current data:\n\n"
        f"{context}\n\n"
        "Answer questions using ONLY this data. If something isn't in the data "
        "provided, say so rather than guessing. Be concise and direct — deans "
        "are busy. Use specific numbers from the data when relevant."
    )

    messages = conversation_history + [{"role": "user", "content": question}]

    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1000,
        system=system_prompt,
        messages=messages,
    )

    return response.content[0].text
