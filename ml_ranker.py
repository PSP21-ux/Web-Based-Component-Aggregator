import re
from sentence_transformers import SentenceTransformer, util

# Load the embedding model
embedder = SentenceTransformer("all-MiniLM-L6-v2")

# Keywords and weights
ACCESSORY_KEYWORDS = ["case", "cover", "cable", "wire", "screw", "holder", "mount", "bracket", "connector", "clip"]
ACCESSORY_PENALTY_WEIGHT = 0.6

ACCESSORY_PENALTY_KEYWORDS = ACCESSORY_KEYWORDS
SIMPLE_PRODUCT_KEYWORDS = ["board", "module", "sensor"]
KIT_PENALTY_KEYWORDS = ["kit", "starter", "guide", "book", "tutorial", "project", "bundle"]

# Words stripped out when building a normalized "core name" for de-duplication grouping
CORE_NAME_IGNORE_WORDS = ["official", "model", "computer", "motherboard", "ram", "single", "plus", "sbc", "desktop"]
_CORE_NAME_PATTERN = re.compile(r'\b(' + '|'.join(CORE_NAME_IGNORE_WORDS) + r')\b')


def clean_text(text):
    return re.sub(r'[^a-zA-Z0-9 ]', '', text.lower().strip())


def extract_core_name(name):
    """Simplify product names for better grouping. Word-boundary-safe so
    substrings inside other words (e.g. 'ram' inside 'dram') aren't stripped."""
    name = clean_text(name)
    name = _CORE_NAME_PATTERN.sub('', name)
    return ' '.join(name.split())


def parse_price(price_str):
    """Parses a price string into a float, or None if unparseable."""
    try:
        return float(price_str.replace(',', '').replace('₹', '').replace('$', '').strip())
    except (ValueError, AttributeError):
        return None


def normalize_prices_in_place(products):
    """
    Min-max normalizes price across the current result set, inverted so
    cheaper items score closer to 1.0. Bounded to [0, 1] regardless of the
    actual price range, unlike a raw 1/price which can spike arbitrarily
    high for very cheap items and dominate the final score.
    """
    parsed = [parse_price(p.get('price', '')) for p in products]
    valid = [pr for pr in parsed if pr is not None]

    if not valid:
        for p in products:
            p['price_score'] = 0.0
        return

    lo, hi = min(valid), max(valid)
    span = (hi - lo) or 1.0  # avoid divide-by-zero when all prices are equal

    for p, pr in zip(products, parsed):
        p['price_score'] = 0.0 if pr is None else 1.0 - ((pr - lo) / span)


def availability_score(status):
    """
    Yes: confirmed in stock.
    Unknown: no explicit signal either way.
    Backorder: confirmed unavailable right now, but still orderable —
               scored better than a hard out-of-stock.
    Out of Stock: confirmed unavailable, no order path — worst case.
    """
    status = (status or "").strip().lower()
    if status == "yes":
        return 1.0
    if status == "backorder":
        return 0.4
    if status == "out of stock":
        return 0.1
    return 0.7  # unknown / anything else


def accessory_penalty(product_name, query):
    """Apply heavier penalty for accessory-like items unless query itself requests accessories."""
    query_lower = query.lower()
    if any(word in query_lower for word in ACCESSORY_PENALTY_KEYWORDS):
        return 0.0
    name_lower = product_name.lower()
    if any(word in name_lower for word in ACCESSORY_PENALTY_KEYWORDS):
        return ACCESSORY_PENALTY_WEIGHT
    return 0.0


def core_product_bonus(product_name, query):
    """
    Bonus for products that look like standalone core items rather than
    accessories or bundles. Generalized across any product family (not
    just Raspberry Pi) by combining two signals:
      1. Absence of accessory/kit language in the name.
      2. How much of the query's own vocabulary appears in the name —
         a tight, high-overlap match is more likely to be the exact
         core product being searched for, versus a loosely related item.
    """
    name_lower = product_name.lower()
    if any(word in name_lower for word in ACCESSORY_KEYWORDS + KIT_PENALTY_KEYWORDS):
        return 0.0

    query_tokens = set(clean_text(query).split())
    name_tokens = set(clean_text(product_name).split())
    if not query_tokens:
        return 0.0

    overlap = len(query_tokens & name_tokens) / len(query_tokens)
    return 0.3 * overlap


def simplicity_bonus(product_name):
    name_lower = product_name.lower()
    if any(word in name_lower for word in KIT_PENALTY_KEYWORDS):
        return -0.2
    if any(word in name_lower for word in SIMPLE_PRODUCT_KEYWORDS):
        return 0.1
    return 0.0


def official_bias(product_name):
    name_lower = product_name.lower()
    return 0.05 if "official" in name_lower else 0.0


def token_match_bonus(product_name, query):
    """Generic token matching bonus. Strips non-alphanumerics from both
    sides first so e.g. 'esp32' vs 'esp-32' still match."""
    product_clean = clean_text(product_name)
    query_clean = clean_text(query)
    query_tokens = query_clean.split()
    bonus = 0.0
    for token in query_tokens:
        if token in product_clean:
            bonus += 0.1
        else:
            bonus -= 0.05
    return bonus


def dynamic_weights(query):
    query_tokens = clean_text(query).split()
    if len(query_tokens) >= 3:
        return {"relevance": 0.5, "price": 0.35, "availability": 0.15}
    else:
        return {"relevance": 0.5, "price": 0.3, "availability": 0.2}


def rank_scraped_products(products, query):
    """Rank products using a combination of semantic, price, availability, and custom heuristics."""
    if not products:
        return []

    weights = dynamic_weights(query)
    query_embedding = embedder.encode(query, convert_to_tensor=True)

    # Embed names only — appending the raw price string added noise without
    # useful semantic signal, since price is already scored separately.
    names = [p['name'] for p in products]
    embeddings = embedder.encode(names, convert_to_tensor=True)

    # Price is normalized relative to the whole result set (bounded [0,1])
    # rather than per-item, so it can't spike arbitrarily and drown out
    # semantic relevance for very cheap items.
    normalize_prices_in_place(products)

    for i, p in enumerate(products):
        p['semantic_score'] = float(util.cos_sim(query_embedding, embeddings[i])[0])
        p['availability_score'] = availability_score(p.get('availability', 'unknown'))

        penalty = accessory_penalty(p['name'], query)
        bonus = (
            simplicity_bonus(p['name']) +
            official_bias(p['name']) +
            token_match_bonus(p['name'], query) +
            core_product_bonus(p['name'], query)
        )

        p['final_score'] = (
            weights['relevance'] * p['semantic_score'] +
            weights['price'] * p['price_score'] +
            weights['availability'] * p['availability_score'] +
            bonus - penalty
        )

    # Group by core name and collapse to top-per-group
    grouped = {}
    for p in products:
        core = extract_core_name(p['name'])
        grouped.setdefault(core, []).append(p)

    deduped = []
    for group in grouped.values():
        sorted_group = sorted(group, key=lambda x: x['final_score'], reverse=True)
        deduped.append(sorted_group[0])

    final_sorted = sorted(deduped, key=lambda x: x['final_score'], reverse=True)

    # Cleanup scoring fields before returning
    for p in final_sorted:
        for key in ['semantic_score', 'price_score', 'availability_score', 'final_score']:
            p.pop(key, None)

    return final_sorted