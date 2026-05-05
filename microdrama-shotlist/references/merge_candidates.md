# Merge Candidates — The Five-Rule Gate

Column E (Merge Candidate) is editor-only metadata. It suggests when two or more atomic rows could collapse into one continuous shot with camera movement, if the human editor prefers that rhythm over hard cuts.

The Prompt formula deliberately skips column E — merge notes don't affect the AI generation.

## The AI's spatial-reasoning caveat

The AI does not have embodied spatial intuition — no sense of lens length, parallax, room geometry, how a handheld push actually feels on a camera operator's shoulder. Merge suggestions come from film grammar conventions (eyeline match, 180-degree rule, reveal pans, rack focus), not from reading the physical space.

The human director has final say. A merge that reads well on paper may feel cramped or disorienting on set. Flag merges as suggestions, not commands.

## The five-rule gate

Merge is appropriate ONLY when ALL FIVE are true:

1. **Same continuous space.** One room, one vehicle, one sightline. No cuts to different locations.
2. **Single camera motion.** Pan, tilt, dolly, push, pull, track, or rack focus. One motion, not compound.
3. **Beat is not HOOK, JOLT, or CLIFF.** Those need hard cuts to land the punch. A smooth pan through a jolt kills the hit.
4. **Not a dialogue exchange.** Two speakers stay cut. Merging them locks you into a stagey two-shot and loses the cross-cutting rhythm.
5. **Merged runtime fits 3–5 seconds.** Soft extension beyond the 4s atomic cap because camera moves need breathing room. Above 5s, you're creating a generation the AI won't handle cleanly.

If any rule fails, don't merge.

## Typical merge types

### Reveal pan / push

Character moves toward something → camera follows → reveals the thing. One motion.

```
43. [MS Handheld] Arif crosses to the kost window and parts the curtain a finger's width.
44. [Insert Handheld Push] Merge w/ 43; handheld push through the parting curtain, landing on the Pajero Sport.
```

### Push-in to information

Subject receives/looks at a phone/screen → camera pushes in → information visible.

```
26. [CU Static] Arif pulls Henry's phone out of the jacket pocket.
27. [Insert Dolly In] Merge w/ 26; continuous push-in from Arif's hand to the phone screen as the notification appears.
```

### Rack focus

Two subjects in the same frame at different depths → focus rack pulls attention from one to the other.

```
66. [Insert Static] Henry's phone buzzes with a new SMS: 'Hapus semuanya. Mereka sudah tahu.'
67. [CU Rack Focus] Merge w/ 66; rack focus from the SMS on Henry's phone to Arif's trembling hands.
```

### OTS push-in (reveal action)

Character reaches for something → camera pushes past shoulder → reveals the action.

```
11. [OTS Static] Over Arif's shoulder into the empty backseat: a cracked iPhone glowing on the leather.
12. [CU Static] Merge w/ 11; OTS push-in as Arif reaches over the seat to pick up the phone.
```

## Format of the merge note

Goes in column E of the LATER of the two merged rows:

```
Merge w/ {earlier shot #}; {camera motion description ending at the current row's subject}.
```

Keep it one sentence. Don't narrate the whole shot — just the motion that links the two rows.

## Target ratio

~10% of shots flagged as merge candidates in a typical episode. For a 70-shot episode, that's 6–8 merges. Outlier episodes with lots of restricted space (one-location thriller, for example) may tilt higher — up to 15%. If you're flagging more than 20%, you're over-suggesting. If less than 5%, you're being too timid.

## What NOT to merge

### Hard cuts on jolts

```
27. [Insert Dolly In] Merge w/ 26; push-in to Rp 70 miliar notification.   ← OK (non-jolt approach shot)
28. [CU Static] Arif's eyes blow wide, mouth falls open.                     ← DO NOT merge (this IS the jolt)
```

The jolt (shot 28) needs to be a hard cut. Merging the push-in-to-reveal WITH the reaction kills the hit.

### Dialogue exchanges

```
9. [CU] Arif yells after Henry.                ← keep cut
10. [CU] Arif slumps back, muttering.          ← keep cut
```

Even though both are the same subject in the same space, the two dialogue lines want editor flexibility to trim timing. Merging them into one shot with a small camera drift would force them into the same beat.

### Performance-beat freezes

```
35. [MS] Arif paces the tiny kost room, phone in hand.
36. [CU] Arif's hand rakes through his hair.
37. [CU] Arif stops mid-pace, a cold thought landing.
```

The mid-pace stop in shot 37 is a performance beat that wants a cut, not a glide-through. The editor's choice of cut rhythm is the thing that sells the dread.

## Workflow

1. Build the fully atomized shotlist first. Don't mark merges while atomizing — they need the full row context.
2. Re-read start to end with the five-rule gate in mind.
3. Flag merges in column E of the later row in each pair.
4. Show the user the flagged rows in a diff/comparison format so they can approve/veto each.
5. Default posture: atomized. Merges are opt-in per shot; when in doubt, don't flag.
