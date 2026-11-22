"""Krishi AI rule-based agents and the Master Coordinator.

Each agent is a plain function that reads the shared knowledge base and returns
markdown findings. The Master Coordinator decides which agents a question
needs, runs them and merges their output into one Bengali answer.
No AI model and no API key is used.
"""
import math
import re
from datetime import datetime, timedelta, timezone

from .knowledge import (DIS, DISEASES, MONTH_BN, MONTH_WORDS, PESTS, PROBLEMS, PST,
                        REGIONS, SEASON_WORDS, SEASONS, SOIL_TYPES, SYMPTOM_LABEL,
                        SYMPTOM_WORDS, TO_DECIMAL, VEG, VEGETABLES, CROP_WORDS)

BN_DIGITS = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")
EN_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
BN_CHAR = "ঀ-৿"
CALL = "উপজেলা কৃষি অফিস বা কৃষি কল সেন্টার **১৬১২৩** (যেকোনো মোবাইল থেকে)"

AGENTS = {
    "coord": ("প্রধান সমন্বয়কারী", "Master Coordinator"),
    "veg": ("সবজি বিশেষজ্ঞ", "Vegetable Expert"),
    "season": ("মৌসুম ও আবহাওয়া", "Season & Weather"),
    "disease": ("রোগ নির্ণয়", "Disease Diagnosis"),
    "pest": ("পোকামাকড় ব্যবস্থাপনা", "Pest Management"),
    "soil": ("মাটি ও সার", "Soil & Fertilizer"),
    "irri": ("সেচ ও খামার ব্যবস্থাপনা", "Irrigation & Farm Mgmt"),
    "solve": ("সমস্যা সমাধানকারী", "Problem Solver"),
    "biz": ("খরচ ও ব্যবসা বিশ্লেষণ", "Business & Cost"),
    "research": ("গবেষণা ও যাচাই", "Research & Verification"),
    "scan": ("লক্ষণ স্ক্যানার", "Symptom Scanner"),
    "plan": ("স্মার্ট চাষ পরিকল্পনাকারী", "Smart Farming Planner"),
}


def bn(x):
    """Show numbers with Bengali digits."""
    if isinstance(x, float):
        x = f"{x:,.0f}" if abs(x) >= 100 else f"{x:,.2f}".rstrip("0").rstrip(".")
    elif isinstance(x, int):
        x = f"{x:,}"
    return str(x).translate(BN_DIGITS)


def num(s, default=0.0):
    """Read a number typed with Bengali or English digits, e.g. '৪০,০০০'."""
    if s is None:
        return default
    s = str(s).translate(EN_DIGITS).replace(",", "").strip()
    m = re.search(r"-?\d+(\.\d+)?", s)
    return float(m.group()) if m else default


def ul(items):
    return "\n".join(f"- {x}" for x in items if x)


def now_dhaka():
    return datetime.now(timezone.utc) + timedelta(hours=6)


def month_season(m):
    if m in (10, 11, 12, 1, 2):
        return "rabi"
    if m in (3, 4, 5, 6):
        return "kharif1"
    return "kharif2"


def first_days(text):
    """First number of days in a crop's duration text, e.g. '৬০ থেকে ৭৫ দিন' -> 60."""
    t = text.translate(EN_DIGITS)
    m = re.search(r"(\d+)", t)
    if not m:
        return 75
    n = int(m.group(1))
    return n * 30 if "মাস" in t[:t.find(m.group(1)) + 12] else n


def month_list(ms):
    return ", ".join(MONTH_BN[m] for m in ms)


# =================================================================== parsing
INTENTS = {
    "season": ["কখন", "কোন মাসে", "কোন মৌসুমে", "মৌসুম", "সময়ে", "লাগাব", "লাগাবো", "লাগাতে", "বুনব", "বুনবো", "বপন", "রোপণ", "কি চাষ", "কী চাষ", "কি লাগা", "কী লাগা", "কোন সবজি"],
    "grow": ["কীভাবে চাষ", "কিভাবে চাষ", "চাষ পদ্ধতি", "চাষাবাদ", "দূরত্ব", "বীজতলা", "চারা", "জাত", "কত দিন", "চাষ করতে", "চাষ করব", "চাষ করবো", "নিয়ম"],
    "soil": ["সার", "মাটি", "ph", "পিএইচ", "কম্পোস্ট", "ভার্মি", "ইউরিয়া", "টিএসপি", "পটাশ", "জৈব", "খৈল", "গোবর"],
    "irri": ["সেচ", "পানি দেব", "পানি দিতে", "পানি দিব", "কতটুকু পানি", "মালচ", "নিষ্কাশন", "ড্রিপ", "কত পানি"],
    "roof": ["ছাদ", "টব", "বারান্দা", "ড্রাম", "রুফটপ", "rooftop"],
    "biz": ["খরচ", "লাভ", "আয়", "দাম", "বাজার", "বিক্রি", "টাকা", "বিনিয়োগ", "লাভজনক"],
    "pest": ["পোকা", "কীট", "মাকড়", "মাছি", "জাব", "লেদা", "থ্রিপস", "দমন"],
    "disease": ["রোগ", "ছত্রাক", "ভাইরাস", "ধসা", "ব্লাইট"],
    "rotation": ["শস্য পর্যায়", "সাথী ফসল", "আন্তঃফসল", "মিশ্র ফসল", "একসাথে কোন"],
    "store": ["সংরক্ষণ", "রাখব কীভাবে", "সংগ্রহোত্তর"],
}
PEST_WORDS = {"জাব পোকা": "aphid", "জাবপোকা": "aphid", "সাদা মাছি": "whitefly", "থ্রিপস": "thrips", "জ্যাসিড": "jassid", "পাতা ফড়িং": "jassid",
              "ডগা ও ফল ছিদ্রকারী": "efsb", "ডগা ছিদ্রকারী": "efsb", "ফল ছিদ্রকারী": "fruit_borer", "কাটুই": "cutworm", "সুড়ঙ্গকারী": "leafminer",
              "মাকড়": "mite", "মাছি পোকা": "fruit_fly", "ফলের মাছি": "fruit_fly", "ডায়মন্ডব্যাক": "dbm", "লেদা পোকা": "armyworm",
              "পামকিন বিটল": "red_pumpkin_beetle", "লাল পোকা": "red_pumpkin_beetle", "কৃমি": "nematode", "নেমাটোড": "nematode", "উইভিল": "sp_weevil"}
DISEASE_WORDS = {"আগাম ধসা": "early_blight", "নাবি ধসা": "late_blight", "মড়ক": "late_blight", "লেট ব্লাইট": "late_blight", "আর্লি ব্লাইট": "early_blight",
                 "পাউডারি": "powdery_mildew", "ডাউনি": "downy_mildew", "অ্যানথ্রাকনোজ": "anthracnose", "এনথ্রাকনোজ": "anthracnose", "চারা ধসা": "damping_off",
                 "ঢলে পড়া রোগ": "bacterial_wilt", "উইল্ট": "bacterial_wilt", "মোজাইক": "mosaic_virus", "পাতা কোঁকড়ানো": "leaf_curl_virus",
                 "শিরা হলুদ": "yvmv", "কন্দ পচা": "rhizome_rot", "পার্পল ব্লচ": "purple_blotch", "নরম পচা": "soft_rot"}


def _scan(text, table):
    """Longest-match lookup of phrases; matched spans are blanked so a short word
    inside a longer phrase is not counted twice."""
    found = []
    for w in sorted(table, key=len, reverse=True):
        if w and w in text:
            found.append(table[w])
            text = text.replace(w, " " * len(w))
    return found, text


def has(t, w):
    """Phrase match that does not start in the middle of a word (so সার is not found in শসার)."""
    return re.search(rf"(?<![{BN_CHAR}a-z]){re.escape(w)}", t) is not None


def parse(q):
    t = " " + q.lower().replace("?", " ").replace("।", " ") + " "
    ctx = {"q": q, "crops": [], "tags": [], "problems": [], "intents": set(), "month": None,
           "season": None, "pests": [], "diseases": [], "now": False}

    # turmeric (হলুদ) is also the word for yellow, so only take it as a crop in clear phrases
    table = {k: v for k, v in CROP_WORDS.items() if v != "turmeric"}
    for w in ["হলুদ চাষ", "হলুদের", "হলুদ গাছ", "হলুদ লাগা", "turmeric", "হলুদ কখন", "হলুদ কীভাবে", "হলুদ কিভাবে"]:
        table[w] = "turmeric"
    crops, rest = _scan(t, table)
    ctx["crops"] = list(dict.fromkeys(crops))

    pests, rest2 = _scan(rest, PEST_WORDS)
    dis, rest2 = _scan(rest2, DISEASE_WORDS)
    ctx["pests"], ctx["diseases"] = list(dict.fromkeys(pests)), list(dict.fromkeys(dis))
    tags, _ = _scan(rest2, SYMPTOM_WORDS)
    ctx["tags"] = list(dict.fromkeys(x for grp in tags for x in grp))

    for key, p in PROBLEMS.items():
        if any(has(rest, w) for w in p["words"]):
            ctx["problems"].append(key)
    for key, words in INTENTS.items():
        if any(has(t, w) for w in words):
            ctx["intents"].add(key)

    for w, m in sorted(MONTH_WORDS.items(), key=lambda x: -len(x[0])):
        if re.fullmatch(r"[a-z]+", w):
            if re.search(rf"\b{w}\b", t):
                ctx["month"] = m
                break
        elif re.search(rf"(?<![{BN_CHAR}]){w}(?:ে|ের|র|মাসে|মাস)?(?![{BN_CHAR}])", t):
            ctx["month"] = m
            break
    for w, s in sorted(SEASON_WORDS.items(), key=lambda x: -len(x[0])):
        if w in t:
            ctx["season"] = s
            break
    if any(w in t for w in ["এখন", "এই মাসে", "এ মাসে", "বর্তমানে", "now"]):
        ctx["now"] = True
        ctx["month"] = ctx["month"] or now_dhaka().month
    return ctx


# ==================================================================== agents
def agent_veg(crop_id):
    """Vegetable Expert: full cultivation guide for one crop."""
    v = VEG[crop_id]
    seasons = ", ".join(SEASONS[s]["bn"] for s in v["seasons"])
    rows = [("মৌসুম", seasons), ("বীজ বপন / বীজতলার সময়", month_list(v["sow"])), ("পদ্ধতি", v["method"]),
            ("দূরত্ব", v["spacing"]), ("ফসল তোলা", v["days"]), ("পানির চাহিদা", v["water"]),
            ("উপযোগী মাটি", v["soil"]), ("ছাদে বা টবে", "করা যায়" if v["rooftop"] else "জমিতে করাই ভালো")]
    table = "| বিষয় | তথ্য |\n|---|---|\n" + "\n".join(f"| {a} | {b} |" for a, b in rows)
    seedbed = "বীজতলা" in v["method"]
    trellis = "মাচা" in v["method"] or "মাচা" in v["spacing"]
    steps = [
        "**জমি তৈরি:** ৩ থেকে ৪টি চাষ ও মই দিয়ে মাটি ঝুরঝুরে করুন, আগাছা ও আগের ফসলের অবশিষ্ট সরিয়ে ফেলুন।",
        "**জৈব সার:** জমি তৈরির সময় ভালোভাবে পচা গোবর বা কম্পোস্ট মেশান। এতে মাটির স্বাস্থ্য ভালো থাকে।",
        "**বীজ:** ভালো মানের, রোগমুক্ত বীজ বা চারা নির্ভরযোগ্য উৎস (বিএডিসি, বারি বা অনুমোদিত ডিলার) থেকে কিনুন। প্যাকেটে মেয়াদ ও জাতের নাম দেখে নিন।",
        ("**বীজতলা:** উঁচু বীজতলায় বীজ বুনুন, হালকা ছায়া ও পরিমিত সেচ দিন। সুস্থ সবল চারা বিকেলে রোপণ করে হালকা সেচ দিন।" if seedbed else
         "**বপন:** নির্দেশিত দূরত্বে সারি বা মাদায় বীজ বুনুন। গজানোর পর দুর্বল চারা তুলে পাতলা করুন।"),
        "**রাসায়নিক সার:** ফসল, মাটির অবস্থা ও গাছের বয়স অনুযায়ী পরিমাণ ঠিক করতে হয়। মাটি পরীক্ষা করে বিএআরসি (BARC) সার সুপারিশ গাইড বা উপজেলা কৃষি অফিসের পরামর্শ অনুযায়ী দিন।",
        f"**সেচ:** পানির চাহিদা {v['water']}। মাটির 'জো' দেখে সেচ দিন, জমিতে পানি জমতে দেবেন না।",
        "**আগাছা ও নিড়ানি:** রোপণের ২ থেকে ৩ সপ্তাহ পর থেকে নিয়মিত নিড়ানি দিন ও গোড়ায় মাটি তুলে দিন।",
        ("**মাচা বা খুঁটি:** লতা বাড়তে শুরু করলেই মাচা দিন। ফল মাটিতে লাগলে পচে যায়।" if trellis or v["family"] == "কুমড়া গোত্র" or crop_id == "tomato" else ""),
        "**পর্যবেক্ষণ:** সপ্তাহে অন্তত ২ বার জমি ঘুরে পাতার উপরে ও নিচে রোগ-পোকা দেখুন।",
    ]
    dis = [f"**{DIS[d]['bn']}** ({DIS[d]['en']}): {DIS[d]['prevent'][0]}" for d in v["diseases"] if d in DIS]
    pst = [f"**{PST[p]['bn']}** ({PST[p]['en']}): {PST[p]['prevent'][0]}" for p in v["pests"] if p in PST]
    md = (f"## {v['bn']} চাষ নির্দেশিকা\n\n{table}\n\n### চাষের ধাপ\n{ul(steps)}\n\n"
          f"### প্রধান রোগ\n{ul(dis) or '- উল্লেখযোগ্য রোগ কম।'}\n\n### প্রধান পোকা\n{ul(pst) or '- উল্লেখযোগ্য পোকা কম।'}\n\n"
          f"### বিশেষ টিপস\n- {v['notes']}")
    return md


def agent_season_month(m):
    """Season & Weather Expert: what to sow in a month."""
    s = month_season(m)
    crops = [v for v in VEGETABLES if m in v["sow"]]
    seedbed = [v for v in crops if "বীজতলা" in v["method"]]
    direct = [v for v in crops if v not in seedbed]
    def rows(vs):
        return "\n".join(f"| {v['bn']} | {v['method']} | {v['days']} |" for v in vs)
    md = f"## {MONTH_BN[m]} মাসে কী লাগাবেন\n\n{MONTH_BN[m]} মাস সাধারণত **{SEASONS[s]['bn']}** মৌসুমের অংশ। {SEASONS[s]['weather']}\n\n"
    if seedbed:
        md += "### বীজতলায় চারা তৈরি বা রোপণ\n| সবজি | পদ্ধতি | ফসল তোলা |\n|---|---|---|\n" + rows(seedbed) + "\n\n"
    if direct:
        md += "### সরাসরি বপন বা রোপণ\n| সবজি | পদ্ধতি | ফসল তোলা |\n|---|---|---|\n" + rows(direct) + "\n\n"
    if not crops:
        md += "এই মাসে নতুন করে লাগানোর মতো সবজি কম। আগের লাগানো ফসলের পরিচর্যা করুন।\n\n"
    md += f"### এই সময়ের আবহাওয়া ঝুঁকি\n{ul(SEASONS[s]['risks'])}"
    return md


def agent_season(s):
    """Season & Weather Expert: crops and risks for a season."""
    S = SEASONS[s]
    crops = [v for v in VEGETABLES if s in v["seasons"]]
    rows = "\n".join(f"| {v['bn']} | {month_list(v['sow'])} | {v['days']} |" for v in crops)
    return (f"## {S['bn']} মৌসুম\n\n**সময়:** {S['period']}\n\n**আবহাওয়া:** {S['weather']}\n\n"
            f"### এই মৌসুমের সবজি\n| সবজি | বপন বা বীজতলার মাস | ফসল তোলা |\n|---|---|---|\n{rows}\n\n### ঝুঁকি ও সতর্কতা\n{ul(S['risks'])}")


def score_items(tags, crop=None, problems=(), named=()):
    """Disease Diagnosis + Pest agents: rank diseases, pests and disorders by symptom match."""
    tags = set(tags)
    boost = {}
    for p in problems:
        for i, c in enumerate(PROBLEMS[p]["causes"]):
            boost[c] = max(boost.get(c, 0), 0.2 - 0.02 * i)  # first listed cause is the most common
    crop_items = set(VEG[crop]["diseases"] + VEG[crop]["pests"]) if crop else set()
    out = []
    for kind, items in (("disease", DISEASES), ("pest", PESTS)):
        for it in items:
            ov = len(tags & set(it["tags"]))
            if not ov and it["id"] not in boost and it["id"] not in named:
                continue
            prec = ov / len(tags) if tags else 0
            rec = ov / len(it["tags"])
            s = 0.6 * prec + 0.4 * rec
            if it["tags"][0] in tags:
                s += 0.1  # the item's most typical sign was seen
            s += boost.get(it["id"], 0)
            if it["id"] in named:
                s += 0.6
            if crop:
                if it["id"] in crop_items:
                    s *= 1.25
                elif "*" not in it["crops"] and crop not in it["crops"]:
                    s *= 0.3
            out.append((s, kind, it, sorted(tags & set(it["tags"]))))
    out.sort(key=lambda x: -x[0])
    return [o for o in out if o[0] >= 0.25 * out[0][0]] if out else out


def severity(top, spread=""):
    high = "বেশি" in top.get("severity", "মাঝারি")
    if spread == "most":
        return "বেশি"
    if spread == "few":
        return "মাঝারি" if high else "কম"
    if spread == "some":
        return "বেশি" if high else "মাঝারি"
    return top.get("severity", "মাঝারি")


def item_name(kind, it):
    return f"{it['bn']} ({it['en']})" + (" - পোকা" if kind == "pest" else "")


def agent_research(kind, it):
    """Research & Verification: safety notes and when to call an expert."""
    lines = []
    if kind == "disease" and it.get("chem"):
        lines.append("রাসায়নিক দমন দরকার হলে শুধু কৃষি সম্প্রসারণ অধিদপ্তরে (DAE) নিবন্ধিত বালাইনাশক, লেবেলের নির্দেশনা মেনে, কৃষি কর্মকর্তার পরামর্শে ব্যবহার করুন।")
    if kind == "pest":
        lines.append("আগে জৈব ও যান্ত্রিক পদ্ধতি নিন। আক্রমণ অর্থনৈতিক ক্ষতির সীমা ছাড়ালে তবেই কৃষি কর্মকর্তার পরামর্শে নিবন্ধিত কীটনাশক ব্যবহার করুন।")
    if it.get("kind") == "ভাইরাসজনিত":
        lines.append("ভাইরাসের কোনো ওষুধ নেই। বাহক পোকা (সাদা মাছি, জাব পোকা) দমন ও আক্রান্ত গাছ সরানোই একমাত্র উপায়।")
    if it.get("kind") == "পুষ্টির অভাব":
        lines.append("পুষ্টির অভাব নিশ্চিত হতে মাটি পরীক্ষা করুন। উপজেলা কৃষি অফিস বা মৃত্তিকা সম্পদ উন্নয়ন ইনস্টিটিউটের (SRDI) মাটি পরীক্ষা সুবিধা নিন।")
    lines += ["রাসায়নিক ব্যবহার করলে মাস্ক, গ্লাভস ও পুরো হাতা জামা পরুন এবং লেবেলে লেখা অপেক্ষাকাল (Pre-harvest interval) শেষ হওয়ার আগে ফসল তুলবেন না।",
              "একাধিক রাসায়নিক নিজে থেকে মিশিয়ে স্প্রে করবেন না।",
              f"সমস্যা দ্রুত ছড়ালে বা নিশ্চিত না হলে আক্রান্ত গাছের নমুনা নিয়ে {CALL}-এ যোগাযোগ করুন।"]
    return lines


def agent_solve_questions(problems, top_kind, top):
    qs = []
    for p in problems:
        qs += PROBLEMS[p]["questions"]
    if not qs:
        qs = ["কোন সবজি আক্রান্ত এবং গাছের বয়স কত?", "লক্ষণ কবে থেকে দেখছেন এবং কতগুলো গাছে?", "সম্প্রতি কোনো সার বা কীটনাশক দিয়েছেন কি?"]
    return list(dict.fromkeys(qs))[:4]


def diagnosis_answer(ctx, crop=None, tags=None, spread="", info=None, report=False):
    """Coordinator output for any crop problem, in the standard farmer format."""
    tags = tags if tags is not None else ctx.get("tags", [])
    problems = ctx.get("problems", [])
    named = list(ctx.get("pests", [])) + list(ctx.get("diseases", []))
    ranked = score_items(tags, crop, problems, named)
    used = ["disease", "pest", "solve", "research"]
    extra_tips = [x for p in problems for x in PROBLEMS[p].get("extra", [])]

    if not ranked:
        md = "## সমস্যার পরিচয়\n\nআপনার দেওয়া তথ্য থেকে নির্দিষ্ট রোগ বা পোকা মেলানো যায়নি।\n\n"
        if extra_tips:
            md += f"### সম্ভাব্য কারণ ও করণীয়\n{ul(extra_tips)}\n\n"
        md += ("### আরও তথ্য দিন\n" + ul(agent_solve_questions(problems, None, None)) +
               "\n\nআরও সঠিক ফলাফলের জন্য **লক্ষণ দিয়ে রোগ নির্ণয়** অংশে ফসল বেছে নিয়ে লক্ষণগুলো টিক দিন।")
        return md, ["solve"]

    top_s, kind, top, matched = ranked[0]
    alts = ranked[1:4]
    crop_name = VEG[crop]["bn"] if crop else "উল্লেখ নেই"
    sev = severity(top, spread)
    cf = min(1.0, 0.45 + 0.15 * len(tags)) if tags else 0.5
    conf = round(min(0.92, top_s) * cf * 100)
    matched_txt = [SYMPTOM_LABEL[m] for m in matched] or ["আপনার বর্ণনার সাথে সাধারণ মিল"]
    if kind == "disease":
        used.append("soil") if top["kind"] in ("পুষ্টির অভাব",) else None
        used.append("irri") if top["id"] in ("water_stress", "waterlogging", "heat_stress") else None

    head = ""
    if report:
        head = ("## লক্ষণ স্ক্যানার রিপোর্ট\n\n"
                f"**ফসলের নাম:** {crop_name}  \n**সম্ভাব্য সমস্যা:** {item_name(kind, top)}"
                + (f" *({top['sci']})*" if top.get("sci") else "") +
                f"  \n**বিকল্প সম্ভাবনা:** {', '.join(it['bn'] for _, _, it, _ in alts) or 'নেই'}  \n"
                f"**মিলের হার:** {bn(conf)}% (লক্ষণ মেলানোর হিসাব, নিশ্চিত রোগনির্ণয় নয়)  \n"
                f"**মাত্রা:** {sev}\n\n")

    table = "| ক্রম | সম্ভাব্য কারণ | ধরন | মিলের হার |\n|---|---|---|---|\n" + "\n".join(
        f"| {bn(i + 1)} | {it['bn']} ({it['en']}) | {'পোকা' if k == 'pest' else it['kind']} | {bn(round(min(0.92, s) * cf * 100))}% |"
        for i, (s, k, it, _) in enumerate(ranked[:4]))

    if kind == "disease":
        what = top["desc"]
        cause = top["cause"]
        now = top["now"]
        prevent = top["prevent"]
        future = top["longterm"]
        kind_txt = top["kind"]
        crops_txt = "অনেক ধরনের সবজি" if "*" in top["crops"] else ", ".join(VEG[c]["bn"] for c in top["crops"] if c in VEG)
    else:
        what = top["damage"]
        cause = f"{top['bn']} পোকার আক্রমণ। জীবনচক্র: {top['life']}"
        now = top["mech"] + top["prevent"][:1]
        prevent = top["prevent"] + top["bio"]
        future = [top["monitor"], "সমন্বিত বালাই ব্যবস্থাপনা (IPM) মেনে চলুন: আগে পর্যবেক্ষণ, তারপর জৈব ও যান্ত্রিক দমন।"]
        kind_txt = "পোকামাকড়"
        crops_txt = "অনেক ধরনের সবজি" if "*" in top["crops"] else ", ".join(VEG[c]["bn"] for c in top["crops"] if c in VEG)

    md = head
    md += f"## সমস্যার পরিচয়\n\nসবচেয়ে সম্ভাব্য: **{item_name(kind, top)}** ({kind_txt})।\n\n"
    md += f"### সম্ভাব্য কারণ\n{cause}\n\n{table}\n\n"
    md += f"### কোন ফসল আক্রান্ত\n{(crop_name + '। ') if crop else ''}এই সমস্যা সাধারণত দেখা যায়: {crops_txt}।\n\n"
    md += f"### লক্ষণ\n{what}\n\n**আপনার বর্ণনার সাথে যা মিলেছে:**\n{ul(matched_txt)}\n\n"
    md += f"### রোগ বা সমস্যার মাত্রা\n**{sev}।** " + ("দ্রুত ব্যবস্থা নিন এবং কৃষি কর্মকর্তাকে জানান।" if sev == "বেশি" else "নিয়মিত পর্যবেক্ষণ করে নিচের ব্যবস্থা নিন।") + "\n\n"
    md += f"### এখন কী করতে হবে\n{ul(now)}\n\n"
    if extra_tips:
        md += f"**আরও যা দেখবেন:**\n{ul(extra_tips)}\n\n"
    md += f"### কীভাবে প্রতিরোধ করবেন\n{ul(prevent)}\n\n"
    md += f"### ভবিষ্যতে কী সতর্কতা নিতে হবে\n{ul(future)}\n\n"
    md += f"### বিশেষজ্ঞের পরামর্শ\n{ul(agent_research(kind, top))}\n\n"
    md += f"### নিশ্চিত হতে এই প্রশ্নগুলো ভাবুন\n{ul(agent_solve_questions(problems, kind, top))}"
    if alts:
        md += "\n\n<details><summary>বিকল্প সম্ভাবনাগুলোর বিস্তারিত</summary>\n\n"
        for s, k, it, mt in alts:
            body = it["desc"] if k == "disease" else it["damage"]
            act = (it["now"] if k == "disease" else it["mech"])[:2]
            md += f"**{it['bn']} ({it['en']})**: {body}\n\n{ul(act)}\n\n"
        md += "</details>"
    return md, list(dict.fromkeys(used))


def agent_soil(ph=None, soil=None):
    """Soil & Fertilizer Expert: soil types, pH and balanced nutrition."""
    md = "## মাটি ও সার ব্যবস্থাপনা\n\n"
    if soil and soil in SOIL_TYPES:
        md += f"**আপনার মাটি ({soil}):** {SOIL_TYPES[soil]}\n\n"
    else:
        md += "### মাটির ধরন\n| মাটি | বৈশিষ্ট্য |\n|---|---|\n" + "\n".join(f"| {k} | {v} |" for k, v in SOIL_TYPES.items() if k != "জানি না") + "\n\n"
    if ph:
        if ph < 5.5:
            t = "মাটি বেশ অম্লীয়। ফসফরাস, ক্যালসিয়াম ও ম্যাগনেসিয়াম কম পাওয়া যায়। মাটি পরীক্ষা করে কৃষি কর্মকর্তার পরামর্শে ডলোচুন প্রয়োগ করুন এবং জৈব সার বাড়ান।"
        elif ph < 6.5:
            t = "হালকা অম্লীয়, বেশিরভাগ সবজির জন্য ভালো।"
        elif ph <= 7.5:
            t = "নিরপেক্ষ, বেশিরভাগ সবজির জন্য উপযোগী।"
        else:
            t = "ক্ষারীয় মাটি। দস্তা, লোহা ও বোরনের অভাব দেখা দিতে পারে। জৈব সার বাড়ান ও মাটি পরীক্ষা করে অণুপুষ্টি দিন।"
        md += f"**pH {bn(ph)}:** {t}\n\n"
    else:
        md += ("### মাটির pH\n| pH | অবস্থা | করণীয় |\n|---|---|---|\n| ৫.৫ এর কম | বেশ অম্লীয় | মাটি পরীক্ষা করে চুন প্রয়োগের পরামর্শ নিন |\n"
               "| ৫.৫ থেকে ৬.৫ | হালকা অম্লীয় | বেশিরভাগ সবজির জন্য ভালো |\n| ৬.৫ থেকে ৭.৫ | নিরপেক্ষ | উপযোগী |\n| ৭.৫ এর বেশি | ক্ষারীয় | জৈব সার বাড়ান, অণুপুষ্টির অভাব দেখুন |\n\n")
    md += ("### জৈব সার\n" + ul([
        "**কম্পোস্ট:** খড়, লতাপাতা, গোবর ও রান্নাঘরের উচ্ছিষ্ট স্তরে স্তরে রেখে ২ থেকে ৩ মাস পচিয়ে তৈরি করুন।",
        "**ভার্মি কম্পোস্ট (কেঁচো সার):** গোবর ও জৈব বর্জ্য কেঁচো দিয়ে পচানো উন্নত সার। চারা ও টবে খুব ভালো।",
        "**পচা গোবর:** কাঁচা গোবর দেবেন না, এতে শিকড় পোড়ে ও পোকা বাড়ে।",
        "**সবুজ সার:** ধৈঞ্চা বা শিম জাতীয় ফসল চাষ করে ফুল আসার আগে মাটিতে মিশিয়ে দিন।",
        "**খৈল:** সরিষার খৈল পচিয়ে ব্যবহার করলে পুষ্টি পাওয়া যায় ও কৃমি কিছুটা কমে।"]) + "\n\n")
    md += ("### পুষ্টির অভাবের লক্ষণ\n| পুষ্টি | লক্ষণ |\n|---|---|\n" + "\n".join(
        f"| {DIS[d]['bn'].replace('এর অভাব', '').replace('ের অভাব', '')} | {DIS[d]['desc']} |" for d in
        ["def_n", "def_p", "def_k", "def_s", "def_mg", "def_zn", "def_b", "def_ca"]) + "\n\n")
    md += ("### রাসায়নিক সার নিয়ে জরুরি কথা\n" + ul([
        "কতটুকু সার লাগবে তা ফসল, মাটির অবস্থা ও গাছের বয়সের উপর নির্ভর করে। মাটি পরীক্ষা ছাড়া অনুমানে বেশি সার দেবেন না।",
        "বিএআরসি (BARC) প্রকাশিত সার সুপারিশ গাইড অনুযায়ী উপজেলা কৃষি অফিস ফসলভিত্তিক মাত্রা বলে দিতে পারে।",
        "ইউরিয়া একবারে না দিয়ে কয়েক কিস্তিতে দিন। টিএসপি ও অন্যান্য সার সাধারণত জমি তৈরির সময় দেওয়া হয়।",
        "জৈব ও রাসায়নিক সার মিলিয়ে সুষম সার ব্যবহার করুন।"]))
    return md


def agent_irri(crop_id=None, season=None, roof=False):
    """Irrigation & Farm Management Agent."""
    md = ""
    if roof:
        md += ("## ছাদে ও টবে সবজি চাষ\n\n" + ul([
            "**টব:** টমেটো, বেগুন, মরিচের জন্য অন্তত ১২ থেকে ১৪ ইঞ্চির টব বা অর্ধেক ড্রাম। শাকের জন্য চওড়া কম গভীর ট্রে যথেষ্ট।",
            "**মাটি:** দোআঁশ মাটির সাথে পচা গোবর বা কম্পোস্ট ও কিছু বালু মিশিয়ে ঝুরঝুরে মিশ্রণ তৈরি করুন। কোকোপিট মেশালে টব হালকা হয়।",
            "**নিষ্কাশন:** টবের নিচে ছিদ্র ও খোয়া বা ইটের টুকরা দিন যাতে পানি না জমে।",
            "**রোদ:** দিনে অন্তত ৫ থেকে ৬ ঘণ্টা রোদ লাগে এমন জায়গায় রাখুন।",
            "**সেচ:** গরমে প্রতিদিন সকাল বা বিকেলে, শীতে মাটি শুকালে সেচ দিন। আঙুল দিয়ে মাটির ভেজা ভাব দেখে নিন।",
            "**মাচা:** লাউ, শিম, করলার জন্য ছাদে বাঁশ বা জিআই তারের মাচা দিন।",
            "**ছাদের সুরক্ষা:** ভারী টবের নিচে ইট বা স্ট্যান্ড দিন, ছাদে পানি জমে যেন ঢালাই নষ্ট না হয়।"])
            + "\n\n### ছাদের জন্য উপযোগী সবজি\n" + ", ".join(v["bn"] for v in VEGETABLES if v["rooftop"]) + "\n\n")
    v = VEG.get(crop_id) if crop_id else None
    md += "## সেচ ও পানি ব্যবস্থাপনা\n\n"
    if v:
        need = {"বেশি": "নিয়মিত বেশি পানি লাগে, তবে গোড়ায় পানি জমতে দেবেন না।",
                "মাঝারি": "মাঝারি পানি লাগে। মাটির জো দেখে সেচ দিন।",
                "কম": "কম পানিতে হয়, অতিরিক্ত সেচে ক্ষতি হয়।"}[v["water"]]
        md += f"**{v['bn']}:** {need}\n\n"
    md += ("| মৌসুম | সেচ পরামর্শ |\n|---|---|\n"
           "| রবি (শীত) | বৃষ্টি কম, তাই মাটি শুকালে সাধারণত ৭ থেকে ১০ দিন পরপর সেচ লাগে। বেলে মাটিতে আরও ঘন ঘন। |\n"
           "| খরিফ-১ (গ্রীষ্ম) | গরমে মাটি দ্রুত শুকায়, ৩ থেকে ৫ দিন পরপর সকাল বা বিকেলে সেচ দিন। মালচিং করুন। |\n"
           "| খরিফ-২ (বর্ষা) | সেচের চেয়ে নিষ্কাশন জরুরি। উঁচু বেড ও নালা রাখুন। বৃষ্টি না হলে তবেই সেচ। |\n\n")
    md += ("### ভালো সেচের নিয়ম\n" + ul([
        "মাটি হাতে মুঠো করলে দলা হয় কিন্তু চাপ দিলে ভেঙে যায়, এই 'জো' অবস্থা সবচেয়ে ভালো।",
        "দুপুরের রোদে সেচ দেবেন না। পাতা ভিজিয়ে নয়, গোড়ায় সেচ দিন।",
        "নালা পদ্ধতি বা ড্রিপ সেচে পানি কম লাগে ও রোগ কম হয়।",
        "খড়, কচুরিপানা বা পলিথিন দিয়ে মালচিং করলে পানি বাঁচে ও আগাছা কমে।",
        "বর্ষায় ১৫ থেকে ২০ সেমি উঁচু বেড ও বেডের মাঝে নালা রাখুন যাতে পানি দ্রুত নেমে যায়।"]) + "\n\n")
    md += ("### শস্য পর্যায় ও সাথী ফসল\n" + ul([
        "একই গোত্রের ফসল (যেমন টমেটো, বেগুন, আলু, মরিচ) একই জমিতে পরপর করবেন না, এতে রোগ ও পোকা বাড়ে।",
        "শিম জাতীয় ফসলের পর পাতা ও ফল জাতীয় সবজি করলে মাটির নাইট্রোজেন কাজে লাগে।",
        "উদাহরণ: রবিতে আলু বা কপি, তারপর খরিফ-১ এ মাচায় কুমড়া জাতীয় সবজি, তারপর খরিফ-২ এ ঢেঁড়স বা ডাঁটা।",
        "মাচার নিচের ছায়ায় আদা বা হলুদ, বেগুনের সারির মাঝে লাল শাক বা ধনিয়া সাথী ফসল হিসেবে করা যায়।",
        "কপির জমির চারপাশে সরিষা ও টমেটোর আশপাশে গাঁদা ফুল ফাঁদ ফসল হিসেবে কাজ করে।"]))
    return md


def agent_biz_general():
    return ("## খরচ ও লাভের হিসাব\n\n" + ul([
        "আমার কাছে আপনার এলাকার আজকের বাজারদর নেই, তাই নিজে থেকে দাম বা ফলন অনুমান করব না।",
        "**স্মার্ট চাষ পরিকল্পনা** অংশে **খরচ ও লাভ ক্যালকুলেটর** আছে। সেখানে আপনার বীজ, সার, শ্রমিক, সেচ ও অন্যান্য খরচ, আশা করা ফলন ও স্থানীয় দাম বসালে মোট বিনিয়োগ, আয়, নিট লাভ ও ব্রেক-ইভেন দাম হিসাব হয়ে যাবে।",
        "স্থানীয় বাজারদর জানতে উপজেলা কৃষি অফিস বা কৃষি বিপণন অধিদপ্তরের (DAM) দামের তথ্য দেখুন।",
        "সব হিসাবই অনুমান। আবহাওয়া, রোগ-পোকা ও বাজারদরের ওঠানামায় আসল ফল ভিন্ন হতে পারে।"])
        + "\n\n### খরচের যে খাতগুলো হিসাবে রাখবেন\n" + ul(["বীজ বা চারা", "জমি তৈরি (চাষ, মই)", "জৈব সার", "রাসায়নিক সার", "সেচ (ডিজেল বা বিদ্যুৎ)",
                                                         "শ্রমিক মজুরি", "বালাই দমন (ফাঁদ, জৈব বালাইনাশক)", "মাচা, খুঁটি, মালচিং", "ফসল তোলা, পরিবহন ও প্যাকেট", "জমির ভাড়া (যদি থাকে)"]))


HELP = ("## আমি কীভাবে সাহায্য করতে পারি\n\nআমি একটি নিয়মভিত্তিক কৃষি পরামর্শক। আপনার প্রশ্নে **ফসলের নাম**, **লক্ষণ** বা **মাস** লিখলে সবচেয়ে ভালো উত্তর দিতে পারি। যেমন:\n\n" + ul([
    "টমেটো গাছের পাতা কুঁকড়ে যাচ্ছে",
    "নভেম্বরে কী সবজি লাগাব?",
    "বেগুনের ডগা ও ফল ছিদ্রকারী পোকা দমন",
    "লাউ চাষ পদ্ধতি",
    "ছাদে টবে কী সবজি করা যায়?",
    "মাটির pH কম হলে কী করব?"]) +
    "\n\nগাছের লক্ষণ মিলিয়ে দেখতে **লক্ষণ দিয়ে রোগ নির্ণয়**, আর জমির পুরো পরিকল্পনার জন্য **স্মার্ট চাষ পরিকল্পনা** অংশ ব্যবহার করুন।")


# ======================================================= Master Coordinator
def coordinate_chat(q):
    """Route a free-text question to the right agents and merge their answers."""
    ctx = parse(q)
    crop = ctx["crops"][0] if ctx["crops"] else None
    it = ctx["intents"]
    parts, used = [], ["coord"]
    problem_mode = bool(ctx["tags"] or ctx["problems"] or ctx["pests"] or ctx["diseases"])
    if problem_mode:
        md, u = diagnosis_answer(ctx, crop=crop)
        parts.append(md)
        used += u
    else:
        if crop and (it & {"grow", "season", "pest", "disease"} or not it):
            parts.append(agent_veg(crop))
            used += ["veg", "season", "pest", "disease"]
            for c in ctx["crops"][1:3]:
                parts.append(agent_veg(c))
        if ctx["month"] and not crop:
            parts.append(agent_season_month(ctx["month"]))
            used.append("season")
        elif ctx["season"] and not crop:
            parts.append(agent_season(ctx["season"]))
            used.append("season")
        elif "season" in it and not crop and not ctx["month"]:
            parts.append(agent_season_month(now_dhaka().month))
            used.append("season")
        if "roof" in it or ("irri" in it) or ("rotation" in it):
            parts.append(agent_irri(crop, ctx["season"], roof="roof" in it))
            used.append("irri")
        if "soil" in it:
            ph = None
            m = re.search(r"(?:ph|পিএইচ)\s*([0-9০-৯.]+)", q.lower())
            if m:
                ph = num(m.group(1), None)
            parts.append(agent_soil(ph))
            used.append("soil")
        if "biz" in it:
            parts.append(agent_biz_general())
            used.append("biz")
        if "store" in it and crop:
            parts.append(f"### সংরক্ষণ\n- {VEG[crop]['notes']}\n- তোলার পর ছায়ায় রেখে মাঠের তাপ কমিয়ে নিন, আঘাতপ্রাপ্ত ও পচা ফসল আলাদা করুন, বাতাস চলাচল করে এমন ঝুড়ি বা ক্রেটে রাখুন।")
    if not parts:
        parts.append(HELP)
    else:
        used.append("research")
        parts.append(f"---\n*এটি সাধারণ নির্দেশনা। জাত, এলাকা ও বছরভেদে সময় ও পরিমাণ বদলাতে পারে। নিশ্চিত হতে {CALL}-এ যোগাযোগ করুন।*")
    return {"answer": "\n\n".join(parts), "agents": list(dict.fromkeys(used)),
            "detected": {"crops": [VEG[c]["bn"] for c in ctx["crops"]],
                         "symptoms": [SYMPTOM_LABEL[t] for t in ctx["tags"]],
                         "month": MONTH_BN.get(ctx["month"]), "season": SEASONS[ctx["season"]]["bn"] if ctx["season"] else None}}


def coordinate_diagnose(crop, tags, spread="", info=None):
    """Symptom scanner flow: scanner -> disease/pest/soil/solve/research -> coordinator."""
    info = info or {}
    tags = [t for t in tags if t in SYMPTOM_LABEL]
    crop = crop if crop in VEG else None
    if not tags:
        return {"answer": "অন্তত একটি লক্ষণ বেছে নিন।", "agents": ["scan"]}
    ctx = {"tags": tags, "problems": [], "pests": [], "diseases": []}
    md, used = diagnosis_answer(ctx, crop=crop, tags=tags, spread=spread, report=True)
    notes = []
    if info.get("chem"):
        notes.append(f"আপনি জানিয়েছেন সম্প্রতি দিয়েছেন: {info['chem']}। অতিরিক্ত সার বা ভুল রাসায়নিকেও পাতা পোড়া, কোঁকড়ানো বা হলুদ হতে পারে, এটি বিবেচনায় রাখুন।")
    if info.get("district"):
        for r in REGIONS.values():
            if any(d in info["district"].lower() for d in r["districts"]):
                notes.append(f"আপনার এলাকা {r['bn']}। ঝুঁকি: {', '.join(r['risks'])}।")
                break
    if notes:
        md += "\n\n### আপনার তথ্য অনুযায়ী বাড়তি সতর্কতা\n" + ul(notes)
    md += f"\n\n---\n*এই রিপোর্ট লক্ষণ মিলিয়ে তৈরি, নিশ্চিত রোগনির্ণয় নয়। আক্রান্ত গাছের নমুনা নিয়ে {CALL}-এ দেখিয়ে নিশ্চিত হোন।*"
    return {"answer": md, "agents": ["coord", "scan"] + used}


def find_region(district):
    d = (district or "").lower()
    for key, r in REGIONS.items():
        if any(x in d for x in r["districts"]):
            return key, r
    return None, None


def coordinate_plan(f):
    """Smart Farming Planner: score crops, then build schedule, calendar, budget and risks."""
    season_map = {"রবি (শীতকাল)": "rabi", "খরিফ-১ (গ্রীষ্ম)": "kharif1", "খরিফ-২ (বর্ষা)": "kharif2"}
    season = season_map.get(f.get("season"))
    if not season:
        season = month_season(now_dhaka().month)
        season_note = f"মৌসুম বলা হয়নি, তাই এখনকার মৌসুম ({SEASONS[season]['bn']}) ধরে পরিকল্পনা করা হয়েছে।"
    else:
        season_note = ""
    unit = f.get("unit", "শতাংশ (ডেসিমাল)")
    land = num(f.get("land"), 0)
    dec = land * TO_DECIMAL.get(unit, 1)
    roof = "টব" in unit
    budget = num(f.get("budget"), 0)
    soil = f.get("soil", "জানি না")
    water = f.get("water", "মাঝারি")
    pref_txt = (f.get("crops") or "").lower()
    pref, _ = _scan(" " + pref_txt + " ", {k: v for k, v in CROP_WORDS.items()})
    pref = set(pref)
    newbie = f.get("exp") == "নতুন"
    commercial = "বাণিজ্যিক" in (f.get("goal") or "") or "দুটোই" in (f.get("goal") or "")
    rkey, region = find_region(f.get("loc"))

    soil_words = {"দোআঁশ": ["দোআঁশ"], "বেলে দোআঁশ": ["বেলে দোআঁশ", "বেলে"], "এঁটেল দোআঁশ": ["দোআঁশ"], "এঁটেল": ["এঁটেল", "ভেজা"], "বেলে": ["বেলে", "চর"]}.get(soil, [])
    rows = []
    for v in VEGETABLES:
        if roof and not v["rooftop"]:
            continue
        if season not in v["seasons"]:
            continue
        sc = {"season": 3.0}
        sc["soil"] = 2.0 if any(w in v["soil"] for w in soil_words) else (1.0 if not soil_words else 0.5)
        w = 1.5
        if water == "কম":
            w = {"বেশি": 0, "মাঝারি": 1, "কম": 2}[v["water"]]
        elif water == "পর্যাপ্ত":
            w = 2
        elif "জলাবদ্ধ" in water:
            w = 2 if v["id"] == "kangkong" else (0.5 if season == "kharif2" else 1.5)
        sc["water"] = w
        high = sum(1 for d in v["diseases"] if d in DIS and "বেশি" in DIS[d]["severity"])
        sc["risk"] = max(0.0, 2 - 0.5 * high - (0.5 * high if newbie else 0))
        days = first_days(v["days"])
        sc["time"] = 1.5 if days <= 60 else (1.0 if days <= 100 else 0.5)
        if not commercial and v["family"] != "" and days > 120:
            sc["time"] -= 0.3
        bonus = 0
        if v["id"] in pref:
            bonus += 2.5
        if rkey == "char" and v["id"] in ("pumpkin", "watermelon", "sweet_potato"):
            bonus += 1
        if rkey == "hill" and v["id"] in ("ginger", "turmeric"):
            bonus += 1
        if rkey == "north" and v["id"] in ("potato", "tomato", "cauliflower", "cabbage"):
            bonus += 0.5
        if rkey == "coastal" and v["id"] in ("pumpkin", "watermelon", "okra", "red_amaranth", "data_shak"):
            bonus += 0.5
        total = sc["season"] + sc["soil"] + sc["water"] + sc["risk"] + sc["time"] + bonus
        rows.append((min(10.0, total / 11.5 * 10), v, sc, high, days, bonus))
    rows.sort(key=lambda r: -r[0])
    if not rows:
        return {"answer": "এই মৌসুম ও জমির জন্য উপযোগী ফসল পাওয়া যায়নি। মৌসুম বা জমির ধরন বদলে আবার চেষ্টা করুন।", "agents": ["coord", "plan"]}
    chosen = [r for r in rows if r[1]["id"] in pref][:3] or rows[:2]
    if len(chosen) < 2:
        chosen += [r for r in rows if r not in chosen][:2 - len(chosen)]
    names = ", ".join(r[1]["bn"] for r in chosen)

    def lvl(x, hi, mid):
        return "ভালো" if x >= hi else ("মাঝারি" if x >= mid else "কম")
    table = "| ফসল | মাটির মিল | পানির মিল | রোগ ঝুঁকি | সময়কাল | মোট স্কোর (১০) |\n|---|---|---|---|---|---|\n" + "\n".join(
        f"| {v['bn']}{' (আপনার পছন্দ)' if v['id'] in pref else ''} | {lvl(sc['soil'], 2, 1)} | {lvl(sc['water'], 2, 1)} | {'বেশি' if h >= 2 else ('মাঝারি' if h == 1 else 'কম')} | {bn(d)}+ দিন | **{bn(round(s, 1))}** |"
        for s, v, sc, h, d, b in rows[:6])

    # land, budget
    land_txt = f"{bn(land)} {unit}" + (f" (প্রায় {bn(round(dec, 1))} শতাংশ)" if unit not in ("শতাংশ (ডেসিমাল)",) and not roof else "")
    per_dec = f"প্রতি শতাংশে প্রায় **{bn(round(budget / dec))} টাকা**" if budget and dec and not roof else ""

    md = "## স্মার্ট চাষ পরিকল্পনা\n\n"
    if season_note:
        md += f"*{season_note}*\n\n"
    md += (f"**অবস্থান:** {f.get('loc') or 'উল্লেখ নেই'}" + (f" ({region['bn']})" if region else "") + "  \n"
           f"**মোট জমি:** {land_txt}  \n**বাজেট:** {bn(int(budget)) + ' টাকা' if budget else 'উল্লেখ নেই'}" + (f" ({per_dec})" if per_dec else "") + "  \n"
           f"**মাটির অবস্থা:** {soil}" + (f", pH {bn(num(f.get('ph')))}" if f.get("ph") else "") + "  \n"
           f"**পানির সুবিধা:** {water}" + (f", {f['irr']}" if f.get("irr") else "") + "  \n"
           f"**মৌসুম:** {SEASONS[season]['bn']}  \n**নির্বাচিত ফসল:** {names}  \n"
           "**প্রস্তাবিত জাত:** বারি উদ্ভাবিত বা অনুমোদিত উন্নত ও হাইব্রিড জাত। আপনার এলাকার জন্য সবচেয়ে ভালো জাতের নাম উপজেলা কৃষি অফিস থেকে জেনে নিন।\n\n")
    md += f"### ফসল তুলনা\nমৌসুম, মাটি, পানি, রোগ ঝুঁকি, সময়কাল ও আপনার পছন্দ মিলিয়ে স্কোর দেওয়া হয়েছে। এটি লাভের নিশ্চয়তা নয়।\n\n{table}\n\n"

    if len(chosen) > 1 and dec and not roof:
        share = round(dec / len(chosen), 1)
        md += f"**জমি ভাগ:** {', '.join(r[1]['bn'] for r in chosen)} প্রতিটিতে প্রায় {bn(share)} শতাংশ। এতে ঝুঁকি ও বাজারদরের ওঠানামা ভাগ হয়ে যায়।\n\n"

    # schedule and calendar per chosen crop
    for s, v, sc, h, days, b in chosen:
        window = {"rabi": [8, 9, 10, 11, 12, 1], "kharif1": [2, 3, 4, 5], "kharif2": [6, 7, 8, 9]}[season]
        sow = [m for m in v["sow"] if m in window] or v["sow"]
        m0 = sow[0]
        seedbed = "বীজতলা" in v["method"]
        nxt = lambda m, k=1: (m - 1 + k) % 12 + 1
        tp = nxt(m0) if seedbed else None
        field = tp or m0
        harvest = nxt(field, max(1, math.ceil(days / 30)))
        md += f"### {v['bn']}: চাষের সময়সূচি\n" + ul([
            f"**জমি তৈরি:** {MONTH_BN[nxt(field, -1)]} মাসের শেষ থেকে {MONTH_BN[field]} মাসের শুরু। চাষ, মই ও পচা জৈব সার মেশানো।",
            f"**বীজ বপন:** {month_list(sow)} ({v['method']})",
            f"**চারা রোপণ:** {MONTH_BN[tp]} মাসে" if seedbed else "**চারা রোপণ:** প্রযোজ্য নয়, সরাসরি বপন",
            f"**দূরত্ব:** {v['spacing']}",
            "**সার পরিকল্পনা:** জমি তৈরির সময় জৈব সার ও মৌলিক সার, পরে কিস্তিতে উপরি সার। পরিমাণ মাটি পরীক্ষা ও কৃষি অফিসের পরামর্শে ঠিক করুন।",
            f"**সেচ পরিকল্পনা:** পানির চাহিদা {v['water']}। " + {"rabi": "৭ থেকে ১০ দিন পরপর বা মাটির জো দেখে।", "kharif1": "৩ থেকে ৫ দিন পরপর, মালচিং করুন।", "kharif2": "নিষ্কাশন আগে, বৃষ্টি না হলে সেচ।"}[season],
            "**পোকা দমন:** " + (", ".join(PST[p]["bn"] for p in v["pests"] if p in PST) or "নিয়মিত পর্যবেক্ষণ") + "। ফেরোমন ও হলুদ আঠালো ফাঁদ, হাতে সংগ্রহ, পরে প্রয়োজনে কৃষি কর্মকর্তার পরামর্শ।",
            "**রোগ প্রতিরোধ:** " + (", ".join(DIS[d]["bn"] for d in v["diseases"] if d in DIS) or "সাধারণ পরিচ্ছন্নতা") + "। রোগমুক্ত বীজ, সঠিক দূরত্ব, পানি নিষ্কাশন।",
            f"**সম্ভাব্য ফসল তোলা:** {MONTH_BN[harvest]} মাস থেকে ({v['days']})"]) + "\n\n"
        cal = []
        if seedbed:
            cal.append((m0, "বীজতলা তৈরি ও বীজ বপন, চারার পরিচর্যা; মূল জমি চাষ শুরু"))
            cal.append((tp, "মূল জমিতে জৈব ও মৌলিক সার, চারা রোপণ, হালকা সেচ"))
        else:
            cal.append((nxt(m0, -1), "জমি তৈরি, জৈব ও মৌলিক সার মেশানো" + (", মাচার উপকরণ জোগাড়" if "মাচা" in v["method"] else "")))
            cal.append((m0, "বীজ বা কাটিং বপন, গজানোর পর পাতলা করা"))
        m = nxt(field)
        while m != harvest:
            cal.append((m, "নিড়ানি, কিস্তিতে উপরি সার, সেচ, ফাঁদ দিয়ে রোগ-পোকা পর্যবেক্ষণ"))
            m = nxt(m)
            if len(cal) > 12:
                break
        cal.append((harvest, "ফসল তোলা শুরু, বাছাই ও বাজারজাত"))
        md += f"**{v['bn']}: মাসভিত্তিক ক্যালেন্ডার**\n\n| মাস | কাজ |\n|---|---|\n" + "\n".join(f"| {MONTH_BN[mm]} | {t} |" for mm, t in cal) + "\n\n"

    md += ("### আর্থিক পরিকল্পনা\n" + ul([
        "আপনার এলাকার আজকের বীজ, সার, মজুরি ও বিক্রয়মূল্য আমার কাছে নেই, তাই নিজে থেকে লাভের অঙ্ক বানাব না।",
        "নিচের **খরচ ও লাভ ক্যালকুলেটরে** আপনার খরচ, আশা করা ফলন ও স্থানীয় দাম বসান। মোট বিনিয়োগ, প্রতি শতাংশে খরচ, আয়, নিট লাভ ও ব্রেক-ইভেন দাম সাথে সাথে হিসাব হবে।",
        (f"আপনার বাজেট {bn(int(budget))} টাকা। মোট খরচ এর চেয়ে বেশি হলে জমির কিছু অংশে কম খরচের ফসল (শাক, ঢেঁড়স) দিয়ে শুরু করুন।" if budget else ""),
        "প্রত্যাশিত ফলনের ধারণা উপজেলা কৃষি অফিস বা অভিজ্ঞ প্রতিবেশী কৃষকের কাছ থেকে নিন এবং কম, মাঝারি ও বেশি তিনভাবে হিসাব করে দেখুন।"]) + "\n\n")

    risks = list(SEASONS[season]["risks"])
    if region:
        risks += region["risks"]
    top_issues = list(dict.fromkeys(DIS[d]["bn"] for r in chosen for d in r[1]["diseases"] if d in DIS and "বেশি" in DIS[d]["severity"]))
    if top_issues:
        risks.append("বড় রোগ ঝুঁকি: " + ", ".join(top_issues))
    risks.append("বাজারদর পড়ে যাওয়া: একাধিক ফসল ও আগাম বা নাবি সময়ে লাগিয়ে ঝুঁকি কমান।")
    prevent = ["রোগমুক্ত বীজ ও সঠিক মৌসুমে রোপণ", "উঁচু বেড, নালা ও মালচিং", "ফেরোমন ও হলুদ আঠালো ফাঁদ দিয়ে শুরু থেকে পর্যবেক্ষণ", "বীজ ও সার আগেই কিনে রাখুন"]
    if region:
        prevent += region["tips"]
    md += (f"### ঝুঁকি ব্যবস্থাপনা\n**প্রধান ঝুঁকি:**\n{ul(risks)}\n\n**প্রতিরোধমূলক ব্যবস্থা:**\n{ul(prevent)}\n\n"
           f"**জরুরি করণীয়:**\n" + ul(["জলাবদ্ধতা হলে সাথে সাথে নালা কেটে পানি বের করুন",
                                      "রোগ দ্রুত ছড়ালে আক্রান্ত গাছ সরিয়ে নমুনাসহ কৃষি অফিসে যান",
                                      f"বড় ক্ষতিতে {CALL}-এ যোগাযোগ করুন"]) + "\n\n")
    why = [f"{SEASONS[season]['bn']} মৌসুমে এই ফসলগুলো উপযোগী।",
           f"আপনার {soil} মাটি ও {water} পানির সুবিধার সাথে এগুলোর মিল ভালো।" if soil != "জানি না" else "মাটির ধরন জানা নেই, মাটি পরীক্ষা করলে পরিকল্পনা আরও সঠিক হবে।"]
    if pref & {r[1]["id"] for r in chosen}:
        why.append("আপনার পছন্দের ফসলকে অগ্রাধিকার দেওয়া হয়েছে।")
    if newbie:
        why.append("নতুন কৃষক হিসেবে কম রোগ ঝুঁকির ফসলকে বেশি স্কোর দেওয়া হয়েছে। প্রথমে ছোট জমিতে শুরু করুন।")
    md += f"### চূড়ান্ত সুপারিশ\n{ul(why)}\n\n---\n*এই পরিকল্পনা সাধারণ নির্দেশনা ও নিয়মভিত্তিক হিসাবের উপর তৈরি। চূড়ান্ত করার আগে {CALL}-এ পরামর্শ নিন।*"
    return {"answer": md, "agents": ["coord", "plan", "veg", "season", "soil", "irri", "pest", "disease", "biz", "research"]}


def calc(f):
    """Business & Cost Analysis: totals, profit and break-even from the farmer's own numbers."""
    items = [("বীজ বা চারা", "seed"), ("জমি তৈরি", "prep"), ("জৈব সার", "org"), ("রাসায়নিক সার", "chemf"), ("সেচ", "irr"),
             ("শ্রমিক", "labour"), ("বালাই দমন", "prot"), ("ফসল তোলা ও পরিবহন", "harvest"), ("প্যাকেট ও অন্যান্য", "other")]
    costs = [(n, num(f.get(k))) for n, k in items]
    total = sum(c for _, c in costs)
    land = num(f.get("land"))
    dec = land * TO_DECIMAL.get(f.get("unit", "শতাংশ (ডেসিমাল)"), 1)
    yld = num(f.get("yield"))
    price = num(f.get("price"))
    revenue = yld * price
    profit = revenue - total
    be = total / yld if yld else 0
    rows = "\n".join(f"| {n} | {bn(round(c))} |" for n, c in costs if c)
    md = (f"### খরচ ও লাভের হিসাব (অনুমান)\n\n| খাত | টাকা |\n|---|---:|\n{rows}\n| **মোট বিনিয়োগ** | **{bn(round(total))}** |\n\n"
          + ul([f"প্রতি শতাংশে খরচ: **{bn(round(total / dec))} টাকা**" if dec else "",
                f"আশা করা উৎপাদন: **{bn(round(yld))} কেজি**" if yld else "",
                f"আশা করা আয়: **{bn(round(revenue))} টাকা** (প্রতি কেজি {bn(price)} টাকা ধরে)" if yld and price else "",
                (f"আশা করা নিট লাভ: **{bn(round(profit))} টাকা**" if profit >= 0 else f"আশা করা লোকসান: **{bn(round(-profit))} টাকা**") if yld and price else "",
                f"ব্রেক-ইভেন দাম: প্রতি কেজি **{bn(round(be, 1))} টাকা**। এর কমে বিক্রি করলে লোকসান হবে।" if yld else "",
                f"বিনিয়োগের তুলনায় লাভ: **{bn(round(profit / total * 100))}%**" if total and yld and price else ""])
          + "\n\n*এগুলো আপনার দেওয়া সংখ্যা থেকে হিসাব করা অনুমান, নিশ্চিত ফলাফল নয়। ফলন ২০% কম হলে বা দাম পড়ে গেলে কী হয় সেটাও একবার হিসাব করে দেখুন।*")
    return {"answer": md, "agents": ["coord", "biz"], "total": total, "profit": profit, "breakeven": be}
