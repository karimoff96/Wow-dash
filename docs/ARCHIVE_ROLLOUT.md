# Telegram archive rollout and restore

## Safety invariant

Local source files may be deleted only when the archive record is `verified`, Telegram returned the same document size, the SHA-256 manifest was saved, and the order-to-archive database transaction committed.

## Rollout

1. Inventory every center: `python manage.py archive --run --all --mode inventory`.
2. Select one center with a configured private channel and run `--mode canary --force`.
3. Open the Telegram message, download the ZIP, extract `archive_manifest.json`, and compare `sha256sum` with the dashboard record.
4. Confirm several order files and receipts open correctly.
5. Run that center with `--mode live --confirm-delete --force`.
6. Observe disk, archive, and error logs for seven days before setting `ARCHIVE_OPERATION_MODE=live`.

## Manual restore drill

1. Open the archive record and follow its Telegram link.
2. Download every part and verify the displayed SHA-256 checksum.
3. Extract the ZIP into an isolated temporary directory; never extract directly over `media/`.
4. Locate the order folder by center order number and compare each file checksum with `archive_manifest.json`.
5. Upload only the required restored files through the authenticated order interface.
6. Record the restore drill date and result in the archive notes.

Archives marked `manual_required` exceeded the automatic Bot API limit. Upload the retained ZIP through Telegram Desktop, then record it without deletion:

```bash
python manage.py verify_manual_archive ARCHIVE_ID \
  --message-id TELEGRAM_MESSAGE_ID \
  --file-id TELEGRAM_FILE_ID \
  --uploaded-size BYTES \
  --sha256 CHECKSUM
```

Perform the restore drill before optionally repeating the command with
`--delete-sources --confirm-delete`. The command refuses missing local archives,
checksum/size mismatches, cross-center manifest orders, and unconfirmed deletion.
