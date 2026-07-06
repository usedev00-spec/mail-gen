"""Realistic, randomised labels for Hide My Email aliases.

Apple pre-fills an alias' label with the website you're signing up for (via
Safari) or lets you type one manually on icloud.com. A fixed label like
"rtuna's gen" on every alias is an obvious fingerprint, so instead we mimic
what a real person's account looks like: a spread of common site/service
names, sometimes as a bare brand, sometimes as a domain, occasionally with a
short context word ("newsletter", "shopping", ...).
"""

import random

# Common consumer sites/services people actually create aliases for. Kept
# broad (shopping, streaming, social, tools, finance, travel, ...) so a run
# doesn't cluster around one category.
_SITES = [
    "Amazon", "eBay", "Etsy", "AliExpress", "Walmart", "Target", "BestBuy",
    "Wish", "Shein", "ASOS", "Zalando", "Nike", "Adidas",
    "Netflix", "Spotify", "Disney+", "Hulu", "HBO Max", "Twitch", "YouTube",
    "SoundCloud", "Deezer", "Audible",
    "Reddit", "Twitter", "Instagram", "Pinterest", "TikTok", "LinkedIn",
    "Discord", "Snapchat", "Tumblr", "Mastodon",
    "Steam", "Epic Games", "PlayStation", "Xbox", "Nintendo", "GOG", "Roblox",
    "Uber", "Lyft", "DoorDash", "Grubhub", "Airbnb", "Booking", "Expedia",
    "Ryanair", "Skyscanner",
    "PayPal", "Revolut", "Wise", "Coinbase", "Binance", "Robinhood",
    "Dropbox", "Notion", "Trello", "Slack", "Figma", "Canva", "GitHub",
    "GitLab", "Medium", "Substack", "Patreon",
    "Duolingo", "Coursera", "Udemy", "Skillshare",
    "IKEA", "Wayfair", "Groupon", "Weoup", "Temu", "Newegg",
    "Grammarly", "LastPass", "NordVPN", "Surfshark", "ProtonMail",
    "Yelp", "TripAdvisor", "Goodreads", "IMDb", "Letterboxd",
]

# Occasional context words appended after a site, like a person jotting down
# what the alias is for.
_CONTEXTS = [
    "newsletter", "signup", "account", "shopping", "promo", "orders",
    "support", "login", "trial", "deals", "updates", "receipts",
]

# Common top-level domains for the "domain" style label.
_TLDS = ["com", "com", "com", "com", "net", "co", "io", "shop"]


def _slug(site: str) -> str:
    """Turn a display name into a plausible domain stem (Disney+ -> disney)."""
    return "".join(ch for ch in site.lower() if ch.isalnum())


def random_alias_label(rng: random.Random | None = None) -> str:
    """Return a single realistic, human-looking alias label.

    Styles are picked at random so a batch looks varied:
      - bare brand:            "Spotify"
      - lowercased brand:      "spotify"
      - domain:                "spotify.com"
      - brand + context:       "Spotify newsletter"
    """
    r = rng or random
    site = r.choice(_SITES)
    style = r.random()

    if style < 0.45:
        # Bare brand name, as typed manually. Occasionally lowercased.
        return site.lower() if r.random() < 0.3 else site
    if style < 0.75:
        # Domain style, as Safari auto-fills from the signup site.
        return f"{_slug(site)}.{r.choice(_TLDS)}"
    # Brand plus a short note about what it's for.
    return f"{site} {r.choice(_CONTEXTS)}"
