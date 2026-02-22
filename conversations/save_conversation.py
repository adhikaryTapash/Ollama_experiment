#!/usr/bin/env python3
"""Save conversation text to a timestamped JSON file in ./conversations/"""
import os
import argparse
import datetime
import json
import uuid
import sys

def save(content, name=None, dir_path="conversations"):
    os.makedirs(dir_path, exist_ok=True)
    ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    uid = uuid.uuid4().hex[:8]
    safe = ""
    if name:
        safe = "".join(c for c in name if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_") + "_"
    filename = f"{safe}{ts}_{uid}.json"
    path = os.path.join(dir_path, filename)
    data = {
        "id": uid,
        "name": name,
        "created_at": datetime.datetime.utcnow().isoformat() + "Z",
        "content": content,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(path)
    return path

def main():
    parser = argparse.ArgumentParser(description="Save conversation text to ./conversations/")
    parser.add_argument("--name", "-n", help="Optional name for the conversation")
    parser.add_argument("--dir", "-d", default="conversations", help="Directory to save conversations")
    parser.add_argument("--file", "-f", help="Read conversation from a file")
    parser.add_argument("--text", "-t", help="Provide conversation text directly")
    args = parser.parse_args()

    if args.file:
        with open(args.file, "r", encoding="utf-8") as fh:
            content = fh.read()
    elif args.text:
        content = args.text
    else:
        # Read from stdin (works with piping or here-doc)
        content = sys.stdin.read()
        if not content:
            parser.error("No content provided. Use --text, --file, or pipe content into the script.")

    save(content, args.name, args.dir)

if __name__ == "__main__":
    main()
