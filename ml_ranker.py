import re
from sentence_transformers import SentenceTransformer, util

# Load the embedding model
embedder = SentenceTransformer("all-MiniLM-L6-v2")

# Keywords and weights
ACCESSORY_KEYWORDS = ["case", "cover", "cable", "wire", "screw", "holder", "mount", "bracket", "connector", "clip"]
ACCESSORY_PENALTY_WEIGHT = 0.6

BOARD_BONUS_PATTERN = re.compile(r'\b(single board computer|compute module|model [345]|raspberry pi [345]|pi [345])\b', re.I)

ACCESSORY_PENALTY_KEYWORDS = ACCESSORY_KEYWORDS
SIMPLE_PRODUCT_KEYWORDS = ["board", "module", "sensor"]
KIT_PENALTY_KEYWORDS = ["kit", "starter", "guide", "book", "tutorial", "project", "bundle"]


def clean_text(text):
    return re.sub(r'[^a-zA-Z0-9 ]', '', text.lower().strip())


def extract_core_name(name):
    """Simplify product names for better grouping."""
    name = clean_text(name)
    keywords_to_ignore = ["official", "model", "computer", "motherboard", "ram", "single", "plus", "sbc", "desktop"]
    for kw in keywords_to_ignore:
        name = name.replace(kw, '')
    return ' '.join(name.split())


def normalize_price(price_str):
    try:
        price = float(price_str.replace(',', '').replace('₹', '').replace('$', '').strip())
        return max(1.0 / price, 0.001)
    except:
        return 0.0


def availability_score(status):
    return 1.0 if status.lower() == "yes" else 0.8


def accessory_penalty(product_name, query):
    """Apply heavier penalty for accessory-like items unless query itself requests accessories."""
    query_lower = query.lower()
    if any(word in query_lower for word in ACCESSORY_PENALTY_KEYWORDS):
        return 0.0
    name_lower = product_name.lower()
    if any(word in name_lower for word in ACCESSORY_PENALTY_KEYWORDS):
        return ACCESSORY_PENALTY_WEIGHT
    return 0.0


def board_bonus(product_name):
    """Boost core board products heavily."""
    return 0.5 if BOARD_BONUS_PATTERN.search(product_name) else 0.0


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
    """Generic token matching bonus."""
    product_name = product_name.lower()
    query = query.lower()
    query_tokens = query.split()
    bonus = 0.0
    for token in query_tokens:
        if token in product_name:
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

    # Compute weights and embeddings
    weights = dynamic_weights(query)
    query_embedding = embedder.encode(query, convert_to_tensor=True)
    names_prices = [f"{p['name']} {p.get('price', '')}" for p in products]
    embeddings = embedder.encode(names_prices, convert_to_tensor=True)

    # Score each product
    for i, p in enumerate(products):
        p['semantic_score'] = float(util.cos_sim(query_embedding, embeddings[i])[0])
        p['price_score'] = normalize_price(p.get('price', ''))
        p['availability_score'] = availability_score(p.get('availability', 'unknown'))

        penalty = accessory_penalty(p['name'], query)
        bonus = (simplicity_bonus(p['name']) + official_bias(p['name']) + token_match_bonus(p['name'], query) + board_bonus(p['name']))

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
        # Optionally penalize outliers
        sorted_group = sorted(group, key=lambda x: x['final_score'], reverse=True)
        top = sorted_group[0]
        deduped.append(top)

    # Final sort across top products
    final_sorted = sorted(deduped, key=lambda x: x['final_score'], reverse=True)

    # Cleanup weights before returning
    for p in final_sorted:
        for key in ['semantic_score', 'price_score', 'availability_score', 'final_score']:
            p.pop(key, None)

    return final_sorted
