# Bludit Themes Repository
Database of themes for [Bludit CMS](https://www.bludit.com).

Add your free or paid theme.

## How to add a new theme
- Create a new folder with the name of the theme. Ex: `clean-blog`
- Capture an screenshot of the Theme. Size `800x600px`, format `PNG`, with the name `screenshot800x600.png`
- Create a metada file with the name of the Theme with the extension JSON. Ex: `clean-blog.json`

Content of the metadata file

```
{
    name: "Clean Blog",
    version: "1.0",
    release_date: "2018-01-11",
    license: "< MIT, GPL-3.0, COMMERCIAL >",
    price_usd: "< PRICE ON USD, IF IT FREE JUST PUT 0 >",
    download_url: "< URL TO DOWNLOAD THE THEME OR LINK TO CHECKOUT >",
    demo_url: "< URL OF THE DEMO >",
    information_url: "< URL OF THE THEME >",
    description: "Description in English",
    features: {
        0: "Feature 1",
        1: "Feature 2",
        2: "Feature 3",
    },
    description_de: "Description in German (optional)",
    features_de: {
        0: "Feature 1 (optional)",
        1: "Feature 2 (optional)",
        2: "Feature 3 (optional)",
    },
    description_es: "Description in Spanish (optional)",
    features_es: {
        0: "Feature 1 (optional)",
        1: "Feature 2 (optional)",
        2: "Feature 3 (optional)",
    },
    author_name: "",
    author_email: "",
    author_contact_url: "",
    author_website: "",
    author_twitter: "",
    author_facebook: "",
    author_github: "",
    author_youtube: "",
    author_reddit: "",
    author_pinterest: "",
    author_flickr: "",
    author_google_plus: "",
    author_vk: ""
}
```
