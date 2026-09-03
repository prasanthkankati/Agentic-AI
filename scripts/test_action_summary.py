import re
import os
from pathlib import Path

AGENT_OUT = Path(__file__).resolve().parents[1] / "agent_outputs"


def summarize_test_file(path: Path):
    text = path.read_text(encoding="utf-8")
    tests = re.split(r"\ndef (?=test_)", "\n" + text)
    summaries = []
    for blk in tests[1:]:
        header, *body = blk.splitlines()
        fn = header.split("(")[0].strip()
        body_text = "\n".join(body)
        actions = []
        if "goto(" in body_text:
            m = re.search(r"goto\(f?\"\{?BASE_URL\}?([^\)\"]*)\"\)", body_text)
            if m:
                actions.append(f"navigate to {m.group(1).strip() or '/'}")
        if ".fill(" in body_text:
            fills = re.findall(r"\.fill\(([^\)]+)\)", body_text)
            for f in fills:
                actions.append(f"fill {f.strip()}")
        if "set_input_files" in body_text:
            files = re.findall(r"set_input_files\(([^\)]+)\)", body_text)
            for fi in files:
                actions.append(f"upload file {fi.strip()}")
        if ".click(" in body_text:
            clicks = body_text.count(".click(")
            actions.append(f"click {clicks} element(s)")
        expects = len(re.findall(r"expect\(|assert ", body_text))
        if expects:
            actions.append(f"assertions: {expects}")

        summaries.append((fn, actions))
    return summaries


def main():
    if not AGENT_OUT.exists():
        print("No agent_outputs directory found.")
        return
    py_files = sorted(AGENT_OUT.glob("test_generated_*.py"))
    if not py_files:
        print("No generated tests found in agent_outputs/")
        return
    for p in py_files:
        print(f"== {p.name} ==")
        for fn, actions in summarize_test_file(p):
            print(f"- {fn}:")
            for a in actions:
                print(f"    - {a}")
        print()


if __name__ == "__main__":
    main()
