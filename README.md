# Manchester CoderDojo website

The source of the [Manchester CoderDojo](https://mcrcoderdojo.org.uk/) website, built using a
static site generator called [beemo](https://github.com/bennuttall/beemo).

## Content

This repo contains content, static files and
[Chameleon](https://chameleon.readthedocs.io/en/latest/) templates for the site.

Blog posts were imported from WordPress using [scripts/wp.py](scripts/wp.py). Events were scraped
from the WordPress site using [scripts/scrape_events.py](scripts/scrape_events.py). Pages were
imported using [scripts/wp_pages.py](scripts/wp_pages.py).

## Build

Requires [beemo](https://github.com/bennuttall/beemo) installed. Log processing additionally requires `beemo[logs]`.

```bash
make build             # build the site
make logs              # process Apache logs into CSV
make analytics         # generate analytics report
make serve             # serve the site locally on port 8000
make serve-analytics   # serve the analytics report on port 8000
```

## Licences

Text content of posts in [content/posts](content/posts/) and pages in
[content/pages](content/pages/) is Copyright the respective authors, licenced under
[CC BY-SA](https://creativecommons.org/licenses/by-sa/4.0/).

The site template and static files are based on the
[Twenty Fourteen](https://wordpress.org/themes/twentyfourteen/) WordPress theme, Copyright 2010
WordPress.org, licenced under [GPL v2](https://www.gnu.org/licenses/old-licenses/gpl-2.0.html).
