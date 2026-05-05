"""Update the Audio/Dialogue global on Video Prompts!B2 across all 6 Sajangnim
episodes. New text reflects the show's trilingual reality (Bahasa + English +
Korean) instead of the prior 'Jakarta Bahasa with Korean code-switch' framing.

B2 (English) and B5 (Bahasa translation) both updated."""
import time
import gspread
from auth import get_credentials

EPISODES = [
    ("Ep 1", "1iygU-7XAwhVKykkTYXHAqwBh0wD1d7Zk2s6OGfnLXCc"),
    ("Ep 2", "1DlnYVqa_6S4ogcaBEtjoWw5tBjrB7wPHjkMFPR5fad4"),
    ("Ep 3", "10wcCajzknstf79pvUs9UuS28ayvVG7k_SPe8KLqyy9I"),
    ("Ep 4", "1khTYtHShiI1z0caqouZUQW3eZKnihScxIG7IQo3l3w4"),
    ("Ep 5", "1_lm-ztYiZKHODRzg0g_N3Ms6HC0Mb8WANjRblVWnnfg"),
    ("Ep 6", "1ZIYUMH_o6PpN1-KDiEiBRT6NZcp1uO6EjEt7L13pQFI"),
]

NEW_AUDIO_EN = (
    "No music. Dialogue is in Bahasa Indonesia, English and Korean — "
    "follow the prompted dialogue closely. Trilingual series. "
    "Documentary editorial sound — no theatrical mix."
)
NEW_AUDIO_ID = (
    "Tanpa musik. Dialog dalam Bahasa Indonesia, Inggris, dan Korea — "
    "ikuti dialog yang dituliskan dengan cermat. Seri trilingual. "
    "Suara dokumenter editorial — tanpa mix teatrikal."
)

print("Cool 60s for sheets quota...", flush=True)
time.sleep(60)
gc = gspread.authorize(get_credentials())

for ep_name, sid in EPISODES:
    print(f"\n=== {ep_name} ===", flush=True)
    try:
        sh = gc.open_by_key(sid)
        sh.values_batch_update(body={
            "valueInputOption": "RAW",
            "data": [
                {"range": "'Video Prompts'!B2", "values": [[NEW_AUDIO_EN]]},
                {"range": "'Video Prompts'!B5", "values": [[NEW_AUDIO_ID]]},
            ],
        })
        print(f"  ✓ B2 (EN audio) updated", flush=True)
        print(f"  ✓ B5 (Bahasa audio) updated", flush=True)
        time.sleep(8)
    except Exception as e:
        print(f"  ! {e}", flush=True)
        time.sleep(15)

print("\n✓ All 6 episodes updated. Reload dashboard + ↻ Refresh to see new global on storyboard cards.", flush=True)
