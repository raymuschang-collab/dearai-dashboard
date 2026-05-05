"""Append one sample carousel post to Raymus_Calendar_v3 Calendar tab."""
from sheets import append_rows

SHEET_ID = "1wX6p9c-gz1tswEcx_wkZP5PjkEMyLUvO8bllh_d9x7M"

HEADERS = [
    "Date", "Day", "Slot", "Tentpole / Series", "Pillar", "Avatar",
    "Audience Focus", "Asset Type", "Video Subtype", "Slide Count (5-8)",
    "Duration (sec)", "Cover / Thumbnail Brief", "Hook", "CTA",
    "Explain Hook", "Conflict", "Solution", "Payoff",
    "Opening Line (17w max)", "VO Script (motion graphic)",
    "Animation Script", "Animation Shot List", "Closing Line",
    "Image Brief", "Body", "Canva Link", "Storyboard Link",
    "Final Asset Link", "LinkedIn Body", "LinkedIn Hashtags",
    "FB Body", "FB Hashtags", "IG Caption", "IG Hashtags",
    "Status", "Approver", "Approved?", "Scheduled Publish",
    "Published URL (LinkedIn)", "Published URL (FB)", "Published URL (IG)",
]

BODY = """\
Slide 1 (Cover): "Microdrama in 6 days. 2 languages. A fraction of traditional cost."

Slide 2 — The old math:
• Traditional short-form drama: 4–6 months from greenlight to delivery
• One language. One market.
• Six-figure budget per episode, minimum.
• You ship it next fiscal year.

Slide 3 — The new math:
• 6 days from script lock to 11 episodes delivered
• Korean + Bahasa Indonesia, same pipeline
• Cost: a fraction — agency-pitchable, not capex-pitchable
• You ship it this campaign cycle.

Slide 4 — What changed (3 things):
1. AI generation handles the visual cost curve
2. A SEA creator network handles the cultural & language layer
3. Tight prep — locked scripts, master templates, no scope drift mid-build

Slide 5 — Why this matters for your Q3/Q4:
• Branded microdrama becomes a line item, not a moonshot
• You can run the same IP in 2 markets without re-shooting
• Your campaign window stops being the bottleneck

Slide 6 — Receipts:
Cyborg (Korean) + Anjing (Bahasa Indonesia) — 11 episodes each — dropped Sat May 2 on PocketShow. Same pipeline. Same week.

Slide 7 — CTA:
DM "PITCH" for the full cost breakdown + a 15-min walk-through of how a branded microdrama ships in your campaign window. Q3 slots opening now.\
"""

IMAGE_BRIEF = """\
Slide 1: Number card. Big "6 DAYS / 2 LANGUAGES" stat. Lucide Regular icon: clock + globe. Bold, high contrast.
Slide 2: Icon card — clock icon, "OLD MATH" label, 4 bulleted lines.
Slide 3: Icon card — zap icon, "NEW MATH" label, 4 bulleted lines (mirror layout to slide 2).
Slide 4: 3-column carousel body — workflow icon top, 3 numbered points.
Slide 5: Icon card — calendar icon, "Q3/Q4 IMPLICATIONS" label.
Slide 6: Photo + quote slide. Raymus face, quote overlay = the receipts text.
Slide 7: CTA card — chat-bubble icon, "DM 'PITCH'" prominent.\
"""

LINKEDIN_BODY = """\
Most AI content demos look weird. This one shipped — in two languages — in a working week.

Cyborg (Korean) and Anjing (Bahasa Indonesia) dropped Saturday on PocketShow. 11 episodes each. Same pipeline. Same week.

The math, swipe →

If you're a brand marketing director or agency CD planning Q3/Q4 and the timeline-and-budget conversation has been frustrating: the line item we're talking about is "branded microdrama in your campaign window," not "AI experiment for next year."

DM "PITCH" for the full cost breakdown.\
"""

FB_BODY = """\
We just shipped 11 episodes of Cyborg (Korean) + 11 episodes of Anjing (Bahasa Indonesia) — same pipeline, same week, fraction of traditional cost. Here's the math behind branded microdrama that fits inside an actual campaign cycle. Swipe through. DM "PITCH" for the breakdown."""

IG_CAPTION = """\
Microdrama in 6 days. 2 languages. The math →

Cyborg + Anjing dropped Saturday. 11 eps each. Same pipeline.

DM "PITCH" for the full cost breakdown.\
"""

LI_TAGS = "#brandedcontent #microdrama #SEAmedia #agencylife #marketingleaders #AIvideo #shortform"
FB_TAGS = "#microdrama #brandedcontent #SEA #PocketShow"
IG_TAGS = "#microdrama #vertical #SEA #brandedcontent #AIvideo #shortform #agencyhacks #PocketShow"

ROW = [
    "2026-05-04",                                                          # Date
    "Mon",                                                                 # Day
    "AM",                                                                  # Slot
    "Channel Launch Week",                                                 # Tentpole / Series
    "Economics",                                                           # Pillar
    "Brand marketing directors / Agency creative directors",               # Avatar
    "Decision-makers in Q3/Q4 planning cycles, budget holders",            # Audience Focus
    "Carousel",                                                            # Asset Type
    "",                                                                    # Video Subtype
    "7",                                                                   # Slide Count (5-8)
    "",                                                                    # Duration (sec)
    "Number card — '6 DAYS / 2 LANGUAGES' stat. Stark contrast vs traditional. Lucide Regular icons (clock + globe).",  # Cover / Thumbnail
    "Microdrama in 6 days, 2 languages. Here's the math.",                 # Hook
    "DM 'PITCH' for the full cost breakdown",                              # CTA
    "Brand directors hear 'AI content' and picture weird demos. The hook reframes: this is shipping math, not novelty.",  # Explain Hook
    "Traditional short-form drama = 4–6 months, single language, six-figure per ep. Budgets are down, expectations are up, and most AI content looks weird.",  # Conflict
    "AI generation + SEA creator network + tight prep = 11 eps in 2 languages, in a working week, at a fraction of traditional cost.",  # Solution
    "Branded microdrama becomes a Q3/Q4 line item — campaign-window-friendly, not 'next fiscal year' moonshot.",  # Payoff
    "Most AI demos look weird. This one shipped — in two languages — in a working week.",  # Opening Line (17w)
    "",                                                                    # VO Script
    "",                                                                    # Animation Script
    "",                                                                    # Animation Shot List
    "Q3 slots opening now — DM 'PITCH'.",                                  # Closing Line
    IMAGE_BRIEF,                                                           # Image Brief
    BODY,                                                                  # Body
    "",                                                                    # Canva Link
    "",                                                                    # Storyboard Link
    "",                                                                    # Final Asset Link
    LINKEDIN_BODY,                                                         # LinkedIn Body
    LI_TAGS,                                                               # LinkedIn Hashtags
    FB_BODY,                                                               # FB Body
    FB_TAGS,                                                               # FB Hashtags
    IG_CAPTION,                                                            # IG Caption
    IG_TAGS,                                                               # IG Hashtags
    "Draft",                                                               # Status
    "Raymus",                                                              # Approver
    "No",                                                                  # Approved?
    "2026-05-04 09:00",                                                    # Scheduled Publish
    "",                                                                    # Published URL (LinkedIn)
    "",                                                                    # Published URL (FB)
    "",                                                                    # Published URL (IG)
]

assert len(ROW) == len(HEADERS), f"Row width mismatch: {len(ROW)} vs {len(HEADERS)}"

if __name__ == "__main__":
    result = append_rows(SHEET_ID, [ROW])
    print("Appended. Updated range:", result.get("updates", {}).get("updatedRange"))
