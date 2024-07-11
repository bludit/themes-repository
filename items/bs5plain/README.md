[![Software License](https://img.shields.io/badge/License-AGPLv3-green.svg?style=flat-square)](LICENSE) [![Bludit 3.15.x](https://img.shields.io/badge/Bludit-3.15.x-blue.svg?style=flat-square)](https://bludit.com)

# bs5plain Theme for Bludit

bs5plain, is a Bootstrap 5 theme for Bludit 3.15.x

## Description

This theme is using the Bootstrap 5.3.x framework. It serves Bootstrap locally and does not use Bludit's included Bootstrap.

bs5plain is reasonably responsive and supports most Bludit 3.15.x features that I've been able to find, including:

* automatic detection of light and dark mode, as configured in the browser
* **sidebar**; sidebar content will be displayed on the off-canvas menu
* **social media links**; social media links will be displayed on the off-canvas menu
* **RSS feed**; the RSS link will be displayed on the off-canvas menu
* **static pages**; these are displayed as buttons at the top of the page
* **static sub pages**; these are _not_ displayed at the top of the page
* **sub pages** are not displayed in the "home" context
* **sub pages** of a page displayed are shown before the page content, below the title
* the **parent page** of a page displayed is shown before the page content, below the title
* **page description**; this is only used for the page's META description, and is not displayed
* **site slogan** and **site description**
* **footer**, if configured in Bludit, will be displayed in, well, the footer
* browsing by tag and category
* **searching for content**; the search box will be displayed on the off-canvas menu if enabled in Bludit
* Bludit's **date format** setting is honored when displaying dates
* no icon kit is used, instead the theme uses Emoji where needed

_The theme contains no tracking code of any kind, nor does it load any external resources_

## Demo

You can see this theme in action on [bludit-bs5plain.joho.se](https://bludit-bs5plain.joho.se)

## Requirements

Bludit version 3.15.x

## Installation

1. Download the latest release from the repository
2. Extract the zip file into a folder, such as `tmp`
3. Upload the `bs5plain` folder to your web server or hosting and put it in the `bl-themes` folder where Bludit is installed
4. Go your Bludit admin page
5. Klick on Themes and activate the `bs5plain` theme

## Changelog

### 1.0.1 (2024-07-11)
* Static pages without a title are no longer displayed in the upper right-hand corner
* The title of the page configured as "Page not found" is no longer displayed
* The page configured as "Page not found" is no longer displayed in the "blog flow" (home)

### 1.0.0 (2024-07-09)
* Initial release

## Other notes

This theme has only been tested with PHP 8.1.x, but should work with other versions too. If you find an issue with your specific PHP version, please let me know and I will look into it.

## License

Please see [LICENSE](LICENSE) for a full copy of AGPLv3.

Copyright 2024 [Joaquim Homrighausen](https://github.com/joho1968); all rights reserved.

This file is part of bs5plain. bs5plain is free software.

bs5plain is free software: you may redistribute it and/or modify it  under
the terms of the GNU AFFERO GENERAL PUBLIC LICENSE v3 as published by the
Free Software Foundation.

bs5plain is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
FITNESS FOR A PARTICULAR PURPOSE. See the GNU AFFERO GENERAL PUBLIC LICENSE
v3 for more details.

You should have received a copy of the GNU AFFERO GENERAL PUBLIC LICENSE v3
along with the bs5plain package. If not, write to:
```
The Free Software Foundation, Inc.,
51 Franklin Street, Fifth Floor
Boston, MA  02110-1301, USA.
```

## Credits

### Logos and graphics

* RSS icon https://commons.wikimedia.org/wiki/File:Antu_application-atom%2Bxml.svg
* Mastodon icon https://commons.wikimedia.org/wiki/File:Mastodon_Logotype_(Simple).svg
* Twitter / X icon https://commons.wikimedia.org/wiki/File:Twitter_new_X_logo.png
* Facebook icon: https://commons.wikimedia.org/wiki/File:Facebook_Logo_2023.png
* Instagram icon: https://commons.wikimedia.org/wiki/File:Instagram_logo_2022.svg
* Xing icon: https://commons.wikimedia.org/wiki/File:Ionicons_logo-xing.svg
* LinkedIn icon: https://commons.wikimedia.org/wiki/File:LinkedIn_icon.svg
* VK icon: https://commons.wikimedia.org/wiki/File:B%26W_Vk_icon.png
* CodePen icon: CodePen
* GitHub icon: GitHub
* GitLab icon: GitLab

### Other credits

* Bootstrap for the [Bootstrap 5](https://getboostrap.com) framework
* Kudos to [Diego Najar](https://github.com/dignajar) for [Bludit](https://bludit.com) :blush:

The bs2plain theme was written by Joaquim Homrighausen while converting :coffee: into code.

The bs5plain theme is sponsored by [WebbPlatsen i Sverige AB](https://webbplatsen.se), Stockholm, :sweden: Commercial support and customizations for this plugin is available from WebbPlatsen i Sverige AB in Stockholm, :sweden:

If you find this plugin useful, the author is happy to receive a donation, good review, or just a kind word.

If there is something you feel to be missing from this plugin, or if you have found a problem with the code or a feature, please do  not hesitate to reach out to support@webbplatsen.se.
