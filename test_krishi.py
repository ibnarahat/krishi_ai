"""Quick self-test. Run: python test_krishi.py"""
from krishi.agents import calc, coordinate_chat, coordinate_diagnose, coordinate_plan
from krishi.knowledge import DIS, PST, VEG


def top(answer):
    return next((l for l in answer.split("\n") if "সবচেয়ে সম্ভাব্য" in l), "")


# every crop's diseases and pests exist in the knowledge base
assert not [x for v in VEG.values() for x in v["diseases"] if x not in DIS]
assert not [x for v in VEG.values() for x in v["pests"] if x not in PST]

assert "Bacterial wilt" in top(coordinate_chat("বেগুন গাছ সবুজ অবস্থায় হঠাৎ ঢলে পড়ছে")["answer"])
assert "TYLCV" in top(coordinate_chat("টমেটো গাছের পাতা কুঁকড়ে যাচ্ছে")["answer"])
assert "Late blight" in top(coordinate_chat("আলুর পাতায় কালচে দাগ, কুয়াশার পর ঝলসে যাচ্ছে")["answer"])
assert "হলুদ চাষ নির্দেশিকা" in coordinate_chat("হলুদ চাষ কখন করব")["answer"]
assert "নভেম্বর মাসে" in coordinate_chat("নভেম্বরে কী সবজি লাগাব")["answer"]
assert "Yellow vein mosaic" in coordinate_diagnose("okra", ["leaf_vein_yellow", "insects_white_fly"])["answer"]
assert "স্মার্ট চাষ পরিকল্পনা" in coordinate_plan({"land": "33", "season": "রবি (শীতকাল)"})["answer"]
r = calc({"seed": "1000", "labour": "1000", "yield": "100", "price": "30", "land": "10"})
assert r["total"] == 2000 and r["profit"] == 1000 and r["breakeven"] == 20
print("All tests passed")
