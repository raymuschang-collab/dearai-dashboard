"""Forward-fill Unspecified sets on Storyboard Prompts!L from the previous
matched set. Microdrama scenes flow — if a set has no environment cues
(all CU face shots), it likely shares the prior set's location."""
import gspread, time
from auth import get_credentials

EPISODES = [
    ("Ep 1", "1iygU-7XAwhVKykkTYXHAqwBh0wD1d7Zk2s6OGfnLXCc"),
    ("Ep 2", "1DlnYVqa_6S4ogcaBEtjoWw5tBjrB7wPHjkMFPR5fad4"),
    ("Ep 3", "10wcCajzknstf79pvUs9UuS28ayvVG7k_SPe8KLqyy9I"),
    ("Ep 4", "1khTYtHShiI1z0caqouZUQW3eZKnihScxIG7IQo3l3w4"),
    ("Ep 5", "1_lm-ztYiZKHODRzg0g_N3Ms6HC0Mb8WANjRblVWnnfg"),
    ("Ep 6", "1ZIYUMH_o6PpN1-KDiEiBRT6NZcp1uO6EjEt7L13pQFI"),
]

print("Cool 90s for quota...", flush=True)
time.sleep(90)

gc = gspread.authorize(get_credentials())
for ep_name, sid in EPISODES:
    print(f"\n=== {ep_name} ===", flush=True)
    try:
        sh = gc.open_by_key(sid)
        sp = sh.worksheet("Storyboard Prompts")
        time.sleep(3)
        col_l = sp.get("L11:L60", value_render_option="FORMATTED_VALUE")
        time.sleep(2)
        # forward-fill
        last_known = ""
        new_l = []
        changed = 0
        for i, row in enumerate(col_l):
            v = (row[0] if row else "").strip()
            if not v:
                new_l.append([""])
                continue
            if v.lower() == "unspecified":
                if last_known:
                    new_l.append([last_known])
                    changed += 1
                else:
                    new_l.append(["Unspecified"])
            else:
                last_known = v
                new_l.append([v])
        if changed:
            sp.update(values=new_l, range_name=f"L11:L{10+len(new_l)}",
                      value_input_option="RAW")
            print(f"  filled {changed} Unspecified → previous match", flush=True)
            for i, v in enumerate(new_l, start=11):
                print(f"    L{i}: {v[0]}", flush=True)
        else:
            print(f"  nothing to fill", flush=True)
        time.sleep(8)
    except Exception as e:
        print(f"  ! {e}", flush=True)
        time.sleep(20)
print("\n✓ done", flush=True)
