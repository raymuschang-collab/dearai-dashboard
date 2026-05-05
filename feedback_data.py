"""
Frame.io feedback for Pharaoh King Assembly (4/30/26).
Extracted from /Users/raymuschang/Downloads/Pharaoh King Assembly - Frame.io - Frame.io.pdf
60 numbered comments from 4 reviewers.

KIND classification:
  regen   → re-prompt this shot's video gen with adjusted instructions
  new     → shot doesn't exist yet, needs to be generated
  edit    → re-edit only (timing, trim, reorder) — no regen needed
  keeper  → reviewer flagged as approved
"""

# (timecode_str, reviewer, comment_num, kind, comment)
COMMENTS = [
    ("01:00:08:21", "CreativesAtWork", 23, "regen",  "too tight. bad lipsync"),
    ("01:00:14:00", "CreativesAtWork", 24, "regen",  "people should be running / falling and the scorpion should bust out and it should be huge"),
    ("01:00:16:03", "Mega",            16, "regen",  "too AI"),
    ("01:00:17:13", "Batara",           1, "regen",  "I think this should be on outside of bazzar, on the battlefield"),
    ("01:00:18:16", "CreativesAtWork", 25, "regen",  "animation too fake"),
    ("01:00:20:03", "CreativesAtWork", 26, "regen",  "too small"),
    ("01:00:29:03", "CreativesAtWork", 27, "regen",  "too small"),
    ("01:00:29:18", "CreativesAtWork", 28, "keeper", "too kaiju but i love it"),
    ("01:00:29:21", "Batara",           2, "regen",  "Too big"),
    ("01:00:40:18", "CreativesAtWork", 29, "regen",  "eyeline of army wrong"),
    ("01:00:40:21", "Batara",           3, "regen",  "Wrong armor"),
    ("01:00:42:10", "CreativesAtWork", 30, "regen",  "shouldnt he be marching. or march then stop"),
    ("01:00:45:00", "Batara",           4, "regen",  "On the background, too chaos, they still haven't fighting yet"),
    ("01:00:47:21", "CreativesAtWork", 31, "edit",   "this has to be previous shot"),
    ("01:00:53:09", "CreativesAtWork", 32, "edit",   "should be in previous shot"),
    ("01:00:56:06", "CreativesAtWork", 33, "regen",  "good size BUT I LIKE BIGGER"),
    ("01:00:58:10", "Rio",             17, "regen",  "the attire is wrong..shud be egyptian armor not sparta"),
    ("01:00:59:03", "Batara",           5, "regen",  "Too small"),
    ("01:01:00:18", "CreativesAtWork", 34, "regen",  "what the fk is this"),
    ("01:01:01:16", "Rio",             18, "regen",  "the spear should be inward not outward"),
    ("01:01:03:12", "Batara",           6, "regen",  "Too small"),
    ("01:01:09:19", "CreativesAtWork", 35, "regen",  "he is looking at the giant scorpion by right"),
    ("01:01:11:14", "Batara",           7, "edit",   "this sequence must be place after the ahmose lose, also in dialog the tehuti mention about tiny scorpion that hasn't even spawn yet"),
    ("01:01:14:04", "Rio",             19, "regen",  "too center no depth"),
    ("01:01:15:09", "CreativesAtWork", 36, "regen",  "they dont feel like they are in the same location but they should be linked by camera movement + captions"),
    ("01:01:21:01", "CreativesAtWork", 37, "regen",  "acting fucked up"),
    ("01:01:29:09", "Rio",             20, "regen",  "the accent shud be egyptian or middle eastern not british"),
    ("01:01:30:07", "CreativesAtWork", 38, "new",    "reaction shot khensu"),
    ("01:01:35:06", "CreativesAtWork", 39, "regen",  "this needs to be OTS tracking, handheld shaky"),
    ("01:01:43:00", "Rio",             21, "regen",  "wrong direction"),
    ("01:01:43:10", "CreativesAtWork", 40, "new",    "he needs to jump while we tilt up towards the pyramid then dissolve"),
    ("01:01:44:17", "CreativesAtWork", 41, "edit",   "we dont need the chariots here"),
    ("01:01:47:13", "CreativesAtWork", 42, "new",    "he says ready here... then show archers stretching the bow"),
    ("01:01:51:15", "CreativesAtWork", 43, "edit",   "or we pan across dead boddies to show army with him infront. then we use this. its quite good"),
    ("01:02:03:00", "CreativesAtWork", 44, "regen",  "SCORPION TOO SMALL"),
    ("01:02:03:00", "Batara",           8, "regen",  "Arrow too big"),
    ("01:02:06:16", "CreativesAtWork", 45, "regen",  "it needs to be shaking / moving then the shell breaks"),
    ("01:02:11:07", "CreativesAtWork", 46, "new",    "fracture then the cracks have these fuckers coming out then we cut to the wide of it big"),
    ("01:02:13:21", "CreativesAtWork", 47, "regen",  "this is great but scorpion too small and the net shots dont make sense"),
    ("01:02:17:03", "Batara",           9, "regen",  "Wrong armor"),
    ("01:02:17:07", "CreativesAtWork", 48, "regen",  "should just cut to the fuckers crawling up the soldiers"),
    ("01:02:22:10", "CreativesAtWork", 49, "edit",   "we need to pan to the general then cut to cu"),
    ("01:02:25:07", "CreativesAtWork", 50, "edit",   "then pan to the city walls"),
    ("01:02:27:13", "Batara",          10, "edit",   "Here, khenzi dialog with the three should be after here. Continue until he comes to battlefield"),
    ("01:02:27:18", "CreativesAtWork", 51, "new",    "tbh him just running into the battlefield is fine. then pan to a broken chariot with the whip underneath. then cut to the whip"),
    ("01:02:35:18", "CreativesAtWork", 52, "new",    "this must go to his face. then he punches his hand in into the sand. then cut to the arm"),
    ("01:02:38:18", "Rio",             22, "edit",   "no need this one yet"),
    ("01:02:40:17", "CreativesAtWork", 55, "edit",   "first cut here"),
    ("01:02:44:07", "Batara",          11, "new",    "Missing shot/scene, battle of khensu and the spawn, where khensu burried in crater as aftermath"),
    ("01:02:45:19", "CreativesAtWork", 53, "regen",  "this shot is wrong"),
    ("01:02:51:06", "CreativesAtWork", 54, "keeper", "this is ok"),
    ("01:03:06:12", "CreativesAtWork", 56, "edit",   "start again from here"),
    ("01:03:07:12", "Mega",            13, "regen",  "looks less miserable"),
    ("01:03:09:00", "CreativesAtWork", 57, "edit",   "start here"),
    ("01:03:20:21", "CreativesAtWork", 58, "regen",  "too small"),
    ("01:03:25:16", "Mega",            14, "regen",  "the tail should be cut off"),
    ("01:03:27:10", "CreativesAtWork", 59, "new",    "needs to jump to his face then freeze"),
    ("01:03:28:05", "CreativesAtWork", 60, "edit",   "we dont need the rest after this"),
    ("01:03:32:18", "Mega",            15, "regen",  "the scene is too bright more than other scene"),
    ("01:03:59:15", "Batara",          12, "regen",  "Too AI"),
]


def tc_to_seconds(tc: str, fps: int = 24) -> float:
    """01:HH:MM:SS:FF → seconds, treating 01:00:00:00 as t=0."""
    parts = tc.split(":")
    h, m, s, f = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
    total = (h - 1) * 3600 + m * 60 + s + f / fps
    return total
