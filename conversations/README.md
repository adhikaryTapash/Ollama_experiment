Save conversation snippets as timestamped JSON files in this folder.

Usage examples:

Save from direct text:

```bash
python conversations/save_conversation.py --name "copilot_chat" --text "Conversation contents..."
```

Save by piping (Linux/macOS/PowerShell supports piping):

```bash
printf '...conversation...' | python conversations/save_conversation.py --name "session1"
```

Save from file:

```bash
python conversations/save_conversation.py --file path/to/file.txt --name "imported"
```

Saved files appear in the `conversations/` folder as timestamped JSON.
