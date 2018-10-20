# Bludit Themes Repository
This repository keeps all the database for the sites:
- (English) https://themes.bludit.com
- (Deutsch) https://themes.bludit.com/de/
- (Español) https://themes.bludit.com/es/

You can add your **free** or **paid** theme here!

## How to add a theme
### 1) Create your username
- Create a new file inside the folder `/authors/`.
- The filename is the username and the extension is `.json`. Please use lowercase without spaces. For example, username `Max Power` the filename is going to be `max-power.json`.
- You can copy a template from `/templates/author.json` to generate the content of the file.

### 2) Create the theme metadata
- Create a new folder with the name of the theme inside the folder `/items/`. Please use lowercase without spaces. For example, the theme name is `Hello World` the folder need to be `/items/hello-world`.
- Create the metadata file `metadata.json` inside the new folder created, you can copy a template from `/templates/item.json` to generate the content of the file.
- Create a screenshot of the theme and put in the folder next to the file `metadata.json`, the filename needs to be `screenshot.png`, size recommended `800x600px`.

If your theme is free, the field `price_usd` need to be `0` otherwise set the price, only the number without the coin type.

## I need help!
If you don't know who to create these folders please contact us in the forum or chat, and we are going to help you.
- Forum: https://forum.bludit.com
- Chat: https://gitter.im/bludit/support
- Facebook: https://www.facebook.com/bluditcms
- Twitter: https://twitter.com/bludit
