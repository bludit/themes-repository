# Bludit Themes Repository
This repository keeps all the database for the sites:
- (English) https://themes.bludit.com
- (Deutsch) https://themes.bludit.com/de/
- (Español) https://themes.bludit.com/es/
- (Русский) https://themes.bludit.com/ru/

You can add your **free** or **paid** theme here!

## How to add a theme
### 1) Create your username
- Create a new file inside the folder `/authors/`.
- The filename is the username and the file extension is `.json`. Please use lowercase without spaces. For example, the username `Max Power` the filename is going to be `max-power.json`.
- You can copy a template from `/templates/author.json` to generate the content of the file.
- Fill in `github` with your GitHub profile, for example `https://github.com/max-power`. It must be the account you open pull requests with: it is how this repository knows which themes are yours.

### 2) Create the theme metadata
- Create a new folder with the name of the theme inside the folder `/items/`. Please use lowercase without spaces. For example, the theme name is `Hello World` the folder is going to be `/items/hello-world`.
- Create a file for the metadata inside the previous folder created, the filename needs to be `metadata.json`, you can copy a template from `/templates/item.json` to generate the content of the file.
- Create a screenshot of the theme and placed next to the file `metadata.json`, the filename needs to be `screenshot.png`, size recommended `800x600px`.

If your theme is free, the field `price_usd` needs to be `0`, otherwise set the price (only the number without the coin type) or set it to `-1` for paid themes with variable or external pricing.

### 3) Open a pull request
A bot checks every pull request and comments with anything that needs fixing. Push a fix and the comment updates.

## Rules checked on every pull request

**Files and folders**
- Theme files go in `items/<theme-name>/` and only two files are allowed there: `metadata.json` and `screenshot.png` (lowercase).
- Author files go in `authors/<username>.json`.
- New folder and file names use lowercase letters, numbers and dashes only.

**`metadata.json`**
- Valid JSON: no trailing commas, no duplicate keys, saved as UTF-8 without BOM.
- Required fields: `name`, `version`, `author_username`, `release_date`, `license`, `price_usd`, `description`, and `download_url` for new themes.
- `author_username` must match a file in `authors/` exactly, including upper and lower case.
- `version` looks like `1.0` or `2.3.1`.
- `release_date` is a real date in `YYYY-MM-DD` format, for example `2026-11-05`, and not in the future.
- `price_usd` is `0`, `-1`, or a price like `9` or `4.99`.
- Links (`download_url`, `demo_url`, `information_url`, …) are full URLs starting with `https://`.
- No template placeholders left, such as `_DESCRIPTION_`.
- Text may only use the tags `<code>`, `<b>`, `<i>`, `<strong>` and `<em>`, without attributes. To show a tag as text, write `&lt;title&gt;`.
- Field names are exactly the ones in `templates/item.json`, in lowercase with underscores (`download_url`, not `downloadUrl` or `Download-URL`). Unknown fields are rejected, and the bot suggests the right name.
- Translations go in `description_de`, `features_de`, `description_es`, `description_ru` (the languages themes.bludit.com shows). Use two-letter language codes; English goes in `description` and `features`.

**`screenshot.png`**
- A real PNG image (not a renamed JPEG), at most 1 MB, between 300x150 and 2400x2400 px. 800x600 px is recommended.

**Author file**
- `name` is required, `github` is required for new authors, and every link starts with `https://`.
- Field names are exactly the ones in `templates/author.json`.

Older themes that don't follow every rule still work. The check only blocks values that a pull request adds or changes; problems that were already there are listed as suggestions.

You can run the same check before opening the pull request:

```
python3 .github/scripts/validate_pr.py --base origin/master --head HEAD --author <your-github-login> --check-links
```

## Review and merge
The bot's comment gives every pull request a verdict:
- 👍 **Ready to merge** (label `ready-to-merge`): every rule above passes, the new links open, the theme will show correctly on themes.bludit.com, and nothing needs a closer look. The comment includes a preview of what the site will show.
- 👍 **Listing OK, waiting for a maintainer review** (label `needs-review`): the files are correct, but a maintainer must check something first. That happens for a new theme (the bot never reads theme code, so a maintainer reviews it), a new author, a change to someone else's theme (translations are very welcome!), a deletion, or a download link moved to a different site. You don't need to do anything unless the maintainer asks.
- 👎 **Not ready to merge** (label `needs-changes`): the comment lists what to fix. Push a fix and the verdict updates.

A maintainer always does the merge.

## I need help!
If you don't know how to create these folders please contact us in the forum or chat, and we are going to help you.
- Discord: https://discord.gg/CFaXEdZWds
- Forum: https://forum.bludit.com
- Chat: https://gitter.im/bludit/support
- Facebook: https://www.facebook.com/bluditcms
- X (ex. Twitter): https://twitter.com/bludit
