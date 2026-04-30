# Sheet Structure — MagicLight Auto v3.0

All three pipeline modes share one sheet. `Row_ID` links them.

## Column Layout (A–W, 23 columns)

| Col | Name | Description |
|-----|------|-------------|
| A | `Row_ID` | Auto-stamped unique lock key — never change after set |
| B | `Status` | `Pending` → `Processing` → `Generated` → `Done` / `Error` |
| C | `Theme` | Story theme (optional) |
| D | `Title` | Story title — used for folder/file naming |
| E | `Story` | **Required** — main story text fed to MagicLight |
| F | `Moral` | Optional moral/constraint |
| G | `Gen_Title` | AI-generated title (output) |
| H | `Gen_Summary` | AI-generated summary (output) |
| I | `Gen_Tags` | AI-generated hashtags (output) |
| J | `Project_URL` | MagicLight project URL (output) |
| K | `Created_Time` | Timestamp when processing started |
| L | `Completed_Time` | Timestamp when generation completed |
| M | `Drive_Link` | Raw video Drive link (Mode 1 output) |
| N | `DriveImg_Link` | Thumbnail Drive link (Mode 1 output) |
| O | `Process_Drive` | Processed video Drive link (Mode 2 output) |
| P | `YT_Status` | `Pending` / `Uploaded` / `Failed` (Mode 3) |
| Q | `YT_Video_ID` | YouTube video ID (Mode 3 output) |
| R | `YT_URL` | YouTube URL (Mode 3 output) |
| S | `YT_Published` | YouTube publish timestamp |
| T | `Credit_Before` | Credits before generation |
| U | `Credit_After` | Credits after generation |
| V | `Email_Used` | Which account processed this row |
| W | `Notes` | Logs, errors, status notes |

## Status Flow

```
Pending → Processing → Generated → Done
                    ↘ No_Video
                    ↘ Error
                    ↘ Low Credit
```

## How to Queue a Story

1. Set `Status` = `Pending`
2. Fill `Story` (required)
3. Fill `Title`, `Theme`, `Moral` (optional but recommended)
4. Run `python main.py --mode 1`

## Initialization

```bash
python main.py --migrate-schema
```
This writes all 23 headers to row 1 automatically.
