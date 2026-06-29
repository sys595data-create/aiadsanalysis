from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class CategoryConfig:
    product: str
    display_name: str
    named_brands: List[str]
    generic_terms: List[str]
    youtube_queries: Dict[str, List[str]]
    tiktok_hashtags: Dict[str, List[str]]
    pipispy_keywords: Dict[str, List[str]]
    minea_keywords: Dict[str, List[str]]
    reddit_terms: Dict[str, List[str]]
    amazon_queries: Dict[str, List[str]]
    trustpilot_domains: List[str]
    walmart_queries: List[str]
    brand_urls: List[str]


CATEGORIES: Dict[str, CategoryConfig] = {
    "eye_massager": CategoryConfig(
        product="EyeSystem",
        display_name="Eye Massager",
        named_brands=["therabody", "smartgoggles", "renpho", "eyeris", "bob brad", "bob & brad", "eyeoasis", "naipo", "breo", "comfier"],
        generic_terms=["eye massager", "eye mask massager", "eye relief device", "eye relaxer", "heated eye mask"],
        youtube_queries={
            "us": ["eye massager review", "best eye massager 2024", "therabody smartgoggles review", "renpho eye massager", "eye strain relief device", "eye migraine massager"],
            "es": ["masajeador de ojos", "máscara masaje ojos", "dispositivo ojos relajación", "masajeador ocular"],
        },
        tiktok_hashtags={
            "us": ["eyemassager", "eyerelief", "eyestrain", "therabody", "renpho", "eyecare", "selfcare"],
            "es": ["masajeadordeojos", "cuidadoojos", "ojoscansados", "bienestar"],
        },
        pipispy_keywords={
            "us": ["eye massager", "eye mask massager", "therabody smartgoggles", "renpho eye", "eye strain relief"],
            "es": ["masajeador ojos", "máscara ojos masaje"],
        },
        minea_keywords={
            "us": ["eye massager", "eye relaxer", "eye strain device", "heated eye mask"],
            "es": ["masajeador ojos", "máscara ocular calor"],
        },
        reddit_terms={
            "us": ["eye massager", "eye strain relief", "migraine eye device", "therabody smartgoggles", "renpho eye", "eye fatigue", "dry eye device"],
            "es": ["masajeador ojos", "fatiga visual", "tensión ocular"],
        },
        amazon_queries={
            "us": ["eye massager", "heated eye massager", "eye mask massager vibration", "therabody smartgoggles"],
            "es": ["masajeador de ojos", "máscara masaje ocular"],
        },
        trustpilot_domains=["therabody.com", "renpho.com"],
        walmart_queries=["eye massager", "heated eye mask massager"],
        brand_urls=["https://www.therabody.com/us/en-us/products/smartgoggles.html", "https://renpho.com/collections/eye-massager"],
    ),

    "circulation_booster": CategoryConfig(
        product="BodyHealth",
        display_name="Circulation Booster / EMS Foot Massager",
        named_brands=["revitive", "nooro", "auvon", "belifu", "tens", "sunmas"],
        generic_terms=["circulation booster", "ems foot massager", "leg circulation device", "foot stimulator", "tens ems device"],
        youtube_queries={
            "us": ["revitive circulation booster review", "EMS foot massager", "leg circulation device", "nooro whole body mat", "foot pain relief device"],
            "es": ["estimulador circulación pies", "masajeador EMS pies", "dispositivo circulación piernas", "revitive revisión"],
        },
        tiktok_hashtags={
            "us": ["revitive", "circulationbooster", "emsmassager", "footpain", "legcirculation", "neuropathy"],
            "es": ["circulacion", "masajeadorpies", "ems", "dolordepies"],
        },
        pipispy_keywords={
            "us": ["revitive circulation booster", "EMS foot massager", "leg circulation", "foot stimulator neuropathy"],
            "es": ["estimulador pies circulación", "masajeador EMS piernas"],
        },
        minea_keywords={
            "us": ["circulation booster", "foot massager EMS", "leg pain relief device"],
            "es": ["estimulador circulación pies", "alivio dolor piernas"],
        },
        reddit_terms={
            "us": ["revitive", "circulation booster", "ems foot", "leg circulation", "neuropathy device", "foot pain relief", "restless leg"],
            "es": ["circulación piernas", "dolor pies", "estimulador EMS"],
        },
        amazon_queries={
            "us": ["revitive circulation booster", "EMS foot massager circulation", "leg foot massager circulation"],
            "es": ["estimulador circulación pies", "masajeador EMS pies piernas"],
        },
        trustpilot_domains=["revitive.com"],
        walmart_queries=["revitive circulation booster", "EMS foot massager"],
        brand_urls=["https://www.revitive.com/revitive-circulation-booster"],
    ),

    "thermal_massage_bed": CategoryConfig(
        product="SpineSystem",
        display_name="Thermal Massage Bed / Jade Mat",
        named_brands=["ceragem", "migun", "healthyline", "biomat", "ereada"],
        generic_terms=["thermal massage bed", "jade roller bed", "far infrared massage table", "jade massage mat", "spine massage device"],
        youtube_queries={
            "us": ["ceragem review", "jade massage bed review", "thermal massage bed back pain", "far infrared massage table", "migun review", "spine decompression device"],
            "es": ["cama masaje jade", "ceragem reseña", "masaje térmico columna", "colchón infrarrojo"],
        },
        tiktok_hashtags={
            "us": ["ceragem", "jademassage", "thermalmassage", "backpainrelief", "spinehealth", "infraredheat"],
            "es": ["ceragem", "masajetermal", "dolorespalda", "camamasaje"],
        },
        pipispy_keywords={
            "us": ["ceragem thermal massage", "jade massage bed", "infrared massage table back pain", "migun bed"],
            "es": ["cama masaje jade infrarrojo", "ceragem España"],
        },
        minea_keywords={
            "us": ["thermal massage bed", "jade roller bed", "spine massager infrared"],
            "es": ["cama masaje jade", "masaje térmico espalda"],
        },
        reddit_terms={
            "us": ["ceragem", "jade massage bed", "thermal massage", "infrared mat", "spine massager", "back pain massage device", "migun"],
            "es": ["ceragem", "cama jade masaje", "masaje térmico espalda"],
        },
        amazon_queries={
            "us": ["jade massage bed infrared", "thermal massage table back", "far infrared massage bed"],
            "es": ["cama masaje jade infrarrojo", "colchoneta masaje térmico"],
        },
        trustpilot_domains=["ceragem.com"],
        walmart_queries=["jade massage mat infrared", "thermal massage bed"],
        brand_urls=["https://ceragem.com/", "https://migun.com/"],
    ),

    "pemf_infrared_mat": CategoryConfig(
        product="SleepSystem",
        display_name="Infrared / PEMF Recovery Mat",
        named_brands=["healthyline", "higher dose", "higherdose", "biomat", "ereada", "sentient element"],
        generic_terms=["PEMF mat", "infrared mat", "far infrared mat", "PEMF therapy device", "infrared heating pad", "grounding mat"],
        youtube_queries={
            "us": ["PEMF mat review", "HigherDOSE infrared mat", "healthyline mat review", "biomat review", "far infrared heating mat", "PEMF therapy at home"],
            "es": ["colchoneta PEMF", "estera infrarroja PEMF", "terapia PEMF casa", "healthyline reseña"],
        },
        tiktok_hashtags={
            "us": ["pemf", "infraredmat", "higherdose", "healthyline", "biomat", "pemftherapy", "biohacking", "recovery"],
            "es": ["pemf", "colchonetainfraro", "bienestar", "recuperacion"],
        },
        pipispy_keywords={
            "us": ["PEMF mat", "HigherDOSE mat", "infrared heating mat PEMF", "biomat", "healthyline mat"],
            "es": ["colchoneta PEMF infrarroja", "estera terapia PEMF"],
        },
        minea_keywords={
            "us": ["PEMF therapy mat", "infrared mat recovery", "HigherDOSE sauna mat"],
            "es": ["colchoneta PEMF", "estera infrarroja calor"],
        },
        reddit_terms={
            "us": ["PEMF mat", "infrared mat", "HigherDOSE", "healthyline", "biomat", "PEMF therapy", "grounding mat", "recovery mat"],
            "es": ["PEMF colchoneta", "estera infrarroja", "terapia PEMF"],
        },
        amazon_queries={
            "us": ["PEMF mat infrared", "far infrared heating mat PEMF", "HigherDOSE infrared mat", "healthyline mat"],
            "es": ["colchoneta infrarroja PEMF", "estera terapia infrarroja"],
        },
        trustpilot_domains=["higherdose.com", "healthyline.com"],
        walmart_queries=["infrared heating mat PEMF", "far infrared mat"],
        brand_urls=["https://higherdose.com/collections/infrared-mats", "https://healthyline.com/"],
    ),
}

# Subreddits for VOC (merged from 595 + voc_scraper)
REDDIT_SUBREDDITS = {
    "us": {
        "general": [
            "biohacking", "longevity", "selfcare", "wellness", "holistic",
            "LifeImprovement", "getdisciplined", "alternativehealth", "naturalhealth",
            "Supplements", "intermittentfasting", "loseit", "nutrition",
        ],
        "field": [
            "ChronicPain", "backpain", "Fibromyalgia", "sleep", "insomnia",
            "massage", "physicaltherapy", "scoliosis", "sciatica", "neuropathy",
            "arthritis", "rheumatoid", "chronicillness", "SpinalCordInjuries",
            "PEMF", "RedLightTherapy", "infraredsauna", "coldplunge",
            "recoverytech", "Meditation", "yoga", "Chiropractic",
        ],
        "competitor": [
            "Therabody", "GarminFitness", "whoop", "ouraring",
            "RecoveryTech", "sleeptech", "Biohacking",
        ],
    },
    "es": {
        "general": ["es", "spain", "AskSpain", "ciudadanos", "actualidad"],
        "field": ["Salud", "Fisioterapia", "bienestares", "dolor_cronico"],
        "competitor": ["tecnologia"],
    },
}

# General wellness influencer search terms (general layer)
GENERAL_SEARCH_TERMS = {
    "us": [
        "Huberman", "Bryan Johnson", "Peter Attia", "Andrew Huberman",
        "biohacking recovery", "longevity protocol", "sleep optimization",
        "red light therapy", "cold plunge benefits", "PEMF therapy benefits",
        "home recovery device", "pain relief technology", "sleep tech",
    ],
    "es": [
        "biohacking", "terapia infrarroja", "recuperación muscular",
        "dispositivo salud casa", "masaje terapéutico", "dolor crónico alivio",
    ],
}
