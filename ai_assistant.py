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
                   breakdown_label="DEPARTMENT BREAKDOWN", consolidation_df=None,
                   expansion_df=None, full_roster_df=None):
    """
    Turns the dataframes already being shown on screen into a plain
    text summary — this is what Claude actually "sees."

    consolidation_df: optional — courses with multiple sections where
    at least one is struggling, shown side by side.

    expansion_df: optional — courses with at least one section that's
    nearly/fully full AND has a meaningful waitlist — candidates for
    ADDING a section, the opposite signal from consolidation.

    full_roster_df: optional — EVERY section in the current scope
    (not just struggling ones), so Claude can answer broader
    questions like "what is Professor X teaching?" instead of only
    knowing about problem sections.
    """
    lines = [f"Enrollment data for: {scope_label}", f"Total sections: {section_count}", ""]
    lines.append(
        "Note: where present, the 'trail' column shows a section's enrollment "
        "over the last 4 snapshots (oldest to newest, e.g. '2 → 2 → 3 → 0'); "
        "'—' means no data existed for that week (the section didn't exist yet). "
        "'total_on_waitlist' shows students currently waiting for a seat — a low-enrolled "
        "section WITH a meaningful waitlist likely has a scheduling problem (wrong time/day), "
        "not a demand problem."
    )
    lines.append("")

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

    if consolidation_df is not None:
        lines.append("")
        lines.append(f"COURSES WITH MULTIPLE SECTIONS WHERE AT LEAST ONE IS STRUGGLING "
                      f"({consolidation_df.groupby(['subject','catalog']).ngroups if len(consolidation_df) > 0 else 0} courses, "
                      f"{len(consolidation_df)} total sections shown below):")
        lines.append("This shows EVERY section of each affected course side by side (both full and "
                      "struggling ones), so you can judge whether a struggling section's students could "
                      "realistically move into a fuller section of the SAME course.")
        if len(consolidation_df) > 0:
            lines.append(consolidation_df.to_string(index=False))
        else:
            lines.append("None")

    if expansion_df is not None:
        lines.append("")
        lines.append(f"COURSES WITH POSSIBLE UNMET DEMAND — at least one section is 90%+ full "
                      f"WITH 3+ students on the waitlist ({expansion_df.groupby(['subject','catalog']).ngroups if len(expansion_df) > 0 else 0} courses, "
                      f"{len(expansion_df)} total sections shown below):")
        lines.append("This shows EVERY section of each affected course. 'high_demand'=True marks the "
                      "specific section(s) that triggered inclusion. Use this to judge whether an "
                      "additional section might be warranted — but note this does NOT account for "
                      "room or faculty availability, which the dean would need to verify separately.")
        if len(expansion_df) > 0:
            lines.append(expansion_df.to_string(index=False))
        else:
            lines.append("None")

    if full_roster_df is not None:
        lines.append("")
        lines.append(f"COMPLETE SECTION ROSTER — EVERY section in this scope, not just struggling "
                      f"ones ({len(full_roster_df)} total). Use this for questions about specific "
                      f"instructors, courses, or sections not mentioned in the lists above:")
        lines.append(full_roster_df.to_string(index=False))

    return "\n".join(lines)


def ask_claude(api_key, context, question, conversation_history):
    """
    Sends the question to Claude, along with the data context and
    any prior turns in this chat (so follow-up questions work).
    """
    client = anthropic.Anthropic(api_key=api_key)

    system_prompt = (
        "You are a helpful assistant for a college dean, answering questions "
        "about their division's enrollment data. Here is the current data:\n\n"
        f"{context}\n\n"
        "Answer questions using ONLY this data. If something isn't in the data "
        "provided, say so rather than guessing. Be concise and direct — deans "
        "are busy. Use specific numbers from the data when relevant.\n\n"
        "IMPORTANT LIMITATION: this data does NOT include meeting days/times, "
        "so when discussing whether sections could be consolidated, you cannot "
        "confirm their schedules don't conflict — mention this as a caveat when "
        "making consolidation suggestions, and recommend the dean verify meeting "
        "times before deciding."
    )

    messages = conversation_history + [{"role": "user", "content": question}]

    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1000,
        system=system_prompt,
        messages=messages,
    )

    return response.content[0].text
