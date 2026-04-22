import re
from typing import Optional

# Country keyword → ISO-2 mapping  (common African + global countries)

COUNTRY_MAP: dict[str, str] = {
    # Africa
    "nigeria": "NG", "nigerian": "NG",
    "benin": "BJ", "beninese": "BJ",
    "ghana": "GH", "ghanaian": "GH",
    "kenya": "KE", "kenyan": "KE",
    "angola": "AO", "angolan": "AO",
    "ethiopia": "ET", "ethiopian": "ET",
    "cameroon": "CM", "cameroonian": "CM",
    "senegal": "SN", "senegalese": "SN",
    "tanzania": "TZ", "tanzanian": "TZ",
    "uganda": "UG", "ugandan": "UG",
    "south africa": "ZA", "south african": "ZA",
    "egypt": "EG", "egyptian": "EG",
    "morocco": "MA", "moroccan": "MA",
    "ivory coast": "CI", "ivorian": "CI",
    "côte d'ivoire": "CI",
    "mozambique": "MZ", "mozambican": "MZ",
    "zambia": "ZM", "zambian": "ZM",
    "zimbabwe": "ZW", "zimbabwean": "ZW",
    "rwanda": "RW", "rwandan": "RW",
    "mali": "ML", "malian": "ML",
    "niger": "NE", "nigerien": "NE",
    "chad": "TD", "chadian": "TD",
    "togo": "TG", "togolese": "TG",
    "somalia": "SO", "somali": "SO",
    "sudan": "SD", "sudanese": "SD",
    "libya": "LY", "libyan": "LY",
    "algeria": "DZ", "algerian": "DZ",
    "tunisia": "TN", "tunisian": "TN",
    "madagascar": "MG", "malagasy": "MG",
    "malawi": "MW", "malawian": "MW",
    "namibia": "NA", "namibian": "NA",
    "botswana": "BW", "botswanan": "BW",
    "gabon": "GA", "gabonese": "GA",
    "congo": "CG", "congolese": "CG",
    "dem rep congo": "CD", "democratic republic of congo": "CD",
    "drc": "CD",
    "sierra leone": "SL",
    "liberia": "LR", "liberian": "LR",
    "guinea": "GN", "guinean": "GN",
    "burkina faso": "BF",
    "mauritania": "MR", "mauritanian": "MR",
    "eritrea": "ER", "eritrean": "ER",
    "djibouti": "DJ",
    "lesotho": "LS",
    "eswatini": "SZ", "swaziland": "SZ",
    "equatorial guinea": "GQ",
    "cape verde": "CV",
    "comoros": "KM",
    "sao tome": "ST",
    "seychelles": "SC",
    "mauritius": "MU",
    "gambia": "GM", "gambian": "GM",
    "guinea-bissau": "GW",
    "central african republic": "CF",
    "south sudan": "SS",
    "burundi": "BI", "burundian": "BI",
    # Other common
    "usa": "US", "united states": "US", "american": "US",
    "uk": "GB", "united kingdom": "GB", "british": "GB",
    "france": "FR", "french": "FR",
    "germany": "DE", "german": "DE",
    "china": "CN", "chinese": "CN",
    "india": "IN", "indian": "IN",
    "brazil": "BR", "brazilian": "BR",
    "canada": "CA", "canadian": "CA",
    "australia": "AU", "australian": "AU",
    "japan": "JP", "japanese": "JP",
}

# Age group keyword → (min_age, max_age, age_group)
AGE_GROUP_MAP = {
    "child": (0, 12, "child"),
    "children": (0, 12, "child"),
    "kid": (0, 12, "child"),
    "kids": (0, 12, "child"),
    "teenager": (13, 17, "teenager"),
    "teenagers": (13, 17, "teenager"),
    "teen": (13, 17, "teenager"),
    "teens": (13, 17, "teenager"),
    "adolescent": (13, 17, "teenager"),
    "adult": (18, 59, "adult"),
    "adults": (18, 59, "adult"),
    "senior": (60, None, "senior"),
    "seniors": (60, None, "senior"),
    "elderly": (60, None, "senior"),
    "old": (60, None, "senior"),
    # "young" is NOT a stored age group — maps to 16-24 per task spec
    "young": (16, 24, None),
    "youth": (16, 24, None),
}


class ParsedQuery:
    def __init__(self):
        self.gender: Optional[str] = None
        self.age_group: Optional[str] = None
        self.min_age: Optional[int] = None
        self.max_age: Optional[int] = None
        self.country_id: Optional[str] = None

    def has_any_filter(self) -> bool:
        return any([
            self.gender,
            self.age_group,
            self.min_age is not None,
            self.max_age is not None,
            self.country_id,
        ])


def parse_nl_query(q: str) -> Optional[ParsedQuery]:
    """
    Parse a natural-language query string into filter params.
    Returns None if the query cannot be interpreted at all.
    """
    if not q or not q.strip():
        return None

    q_lower = q.lower().strip()
    result = ParsedQuery()

    # 1. Gender detection
    if re.search(r'\bmales?\b', q_lower):
        result.gender = "male"
    elif re.search(r'\bfemales?\b', q_lower):
        result.gender = "female"
    elif re.search(r'\bmen\b|\bman\b', q_lower):
        result.gender = "male"
    elif re.search(r'\bwomen\b|\bwoman\b', q_lower):
        result.gender = "female"
    # "male and female" → no gender filter (both)
    if re.search(r'\bmale and female\b|\bfemale and male\b', q_lower):
        result.gender = None

    for keyword, (mn, mx, grp) in AGE_GROUP_MAP.items():
        pattern = r'\b' + re.escape(keyword) + r'\b'
        if re.search(pattern, q_lower):
            if grp:
                result.age_group = grp
            if mn is not None and result.min_age is None:
                result.min_age = mn
            if mx is not None and result.max_age is None:
                result.max_age = mx
            break

    above_match = re.search(r'\b(?:above|over|older than|greater than)\s+(\d+)\b', q_lower)
    if above_match:
        result.min_age = int(above_match.group(1))
        # Always clear descriptive max_age when explicit "above N" is provided
        result.max_age = None

    below_match = re.search(r'\b(?:below|under|younger than|less than)\s+(\d+)\b', q_lower)
    if below_match:
        result.max_age = int(below_match.group(1))

    between_match = re.search(r'\bbetween\s+(\d+)\s+and\s+(\d+)\b', q_lower)
    if between_match:
        result.min_age = int(between_match.group(1))
        result.max_age = int(between_match.group(2))

    sorted_countries = sorted(COUNTRY_MAP.keys(), key=len, reverse=True)
    for country_keyword in sorted_countries:
        pattern = r'\b' + re.escape(country_keyword) + r'\b'
        if re.search(pattern, q_lower):
            result.country_id = COUNTRY_MAP[country_keyword]
            break

    if not result.country_id:
        from_match = re.search(r'\bfrom\s+([a-z\s]+?)(?:\s+(?:above|below|over|under|between|aged?|who|that|$))', q_lower)
        if from_match:
            country_text = from_match.group(1).strip()
            for country_keyword in sorted_countries:
                if country_keyword in country_text:
                    result.country_id = COUNTRY_MAP[country_keyword]
                    break

    if not result.has_any_filter():
        return None

    return result