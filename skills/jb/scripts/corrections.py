import argparse
import sys
from pathlib import Path

import apply_plan
import config
import storage
import genres


def main():
    parser = argparse.ArgumentParser()
    config.arguments(parser)
    args = parser.parse_args()

    draft = storage.in_progress(args.type, "check", args.target)
    if not draft.is_file():
        print(f"No Corrections draft: {draft}")
        sys.exit(2)
    content = storage.read_json(draft)["corrections"]
    root = Path(content["folder"]).resolve()
    ops = genres.by_name(content.get("genre")).with_companions(apply_plan.operations(root, content))
    errors = apply_plan.check(root, ops, [apply_plan.set_aside_folder(args.type).resolve()])
    errors += storage.extension_errors(content)
    errors += [f"missing reason: {m['from']}" for m in content.get("set_aside", []) if not m.get("reason")]
    if errors:
        print("Corrections refused:")
        for error in errors:
            print(f"  {error}")
        sys.exit(1)

    file = storage.corrections(args.type, args.target)
    storage.write_json(file, content)
    draft.unlink()
    print(f"Corrections: {file}")
    print(f"{len(content.get('operations', []))} rename(s), {len(content.get('set_aside', []))} Set aside")


if __name__ == "__main__":
    config.run_main(main)
