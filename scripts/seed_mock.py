"""模拟数据播种工具：向运行中的后端（默认 http://localhost:8000）清库并播种
演示/负载世界——20 人物 / 8 功法 / 6 门派 / 20 物体 / 20 地点 / 80 事件 / 40 概念
+ 208 关系。仅操作运行中服务的开发库，e2e 各自使用独立临时库不受影响。
请求按 --workers 并发（实体先于关系；同阶段内并发，SQLite 单写者由后端排队）。

用法: uv run python scripts/seed_mock.py [--base http://localhost:8000] [--workers 4]
"""

import argparse
import json
import random
import urllib.request
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import TypeVar

CHAR_NAMES = [
    "林长风", "苏晚晴", "叶青崖", "萧子衿", "陆云深", "沈若尘", "顾惊鸿", "白照影",
    "秦寒山", "江望舒", "林听雨", "苏渡寒", "叶疏影", "萧折玉", "陆扶摇", "沈栖梧",
    "顾星阑", "白暮雪", "秦流萤", "江知许",
]
SKILLS = ["玄天诀", "碧波掌法", "御风术", "千机变", "焚天诀", "寒冰真经", "幻影身法", "雷音剑法"]
FACTIONS = ["青云门", "天机阁", "万象宗", "流云寨", "玄冰谷", "赤焰盟"]
ITEMS = [
    "青铜镜", "玉骨笛", "赤霄剑", "乾坤袋", "夜明珠", "残卷地图", "镇魂钟", "碧水珠",
    "乌金甲", "摄魂幡", "紫金葫芦", "龙纹玉佩", "断岳斧", "流云梭", "引雷符", "霜华扇",
    "噬魂珠", "玄龟盾", "织梦梭", "焚香炉",
]
LOCATIONS = [
    "青云山", "落雁谷", "寒潭洞", "沉星湖", "赤焰谷", "天绝崖", "白帝城", "黑风林",
    "碧水镇", "乱星海", "幽冥涧", "万兽原", "栖霞岭", "断魂桥", "望月台", "藏剑山庄",
    "枯骨滩", "百花洲", "镇妖塔", "归墟",
]
CONCEPTS = [
    "因果", "宿命", "执念", "心魔", "天命", "情劫", "道义", "背叛", "救赎", "轮回",
    "谎言", "忠诚", "欲望", "恐惧", "贪婪", "牺牲", "复仇", "宽恕", "传承", "叛逆",
    "秩序", "混沌", "离别", "重逢", "误会", "真相", "秘密", "代价", "选择", "成长",
    "堕落", "觉醒", "羁绊", "孤勇", "幻灭", "希望", "誓言", "遗忘", "执迷", "释然",
]


class Api:
    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")

    def get(self, path: str):
        with urllib.request.urlopen(self.base + path) as r:
            return json.load(r)

    def post(self, path: str, payload: dict) -> dict:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            self.base + path, data=body, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as r:
            assert r.status == 201, (r.status, path)
            return json.load(r)

    def delete(self, path: str) -> None:
        req = urllib.request.Request(self.base + path, method="DELETE")
        with urllib.request.urlopen(req) as r:
            assert r.status == 204


T = TypeVar("T")
R = TypeVar("R")


def _parallel(fn: Callable[[T], R], items: Sequence[T], workers: int) -> list[R]:
    """并发映射并保持提交顺序（workers<=1 退化为串行，便于排障）。"""
    if workers <= 1 or len(items) <= 1:
        return [fn(x) for x in items]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(fn, items))


def reset(api: Api, workers: int) -> None:
    _parallel(lambda r: api.delete(f"/api/relations/{r['id']}"), api.get("/api/relations"), workers)
    _parallel(lambda e: api.delete(f"/api/entities/{e['id']}"), api.get("/api/entities"), workers)


def pick(arr, i):
    return arr[i % len(arr)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://localhost:8000")
    parser.add_argument("--workers", type=int, default=4, help="并发请求数（默认 4）")
    args = parser.parse_args()
    api = Api(args.base)
    workers = args.workers
    random.seed(42)

    reset(api, workers)

    char_ids = _parallel(
        lambda pair: api.post("/api/entities", {
            "type": "character", "name": pair[1], "aliases": [], "audience_known": pair[0] % 2 == 0,
        })["id"],
        list(enumerate(CHAR_NAMES)),
        workers,
    )

    def rand_chars(n):
        return [random.choice(char_ids) for _ in range(n)]

    payloads = []
    for name in SKILLS:
        payloads.append({"type": "skill", "name": name, "aliases": [], "audience_known": True})
    for name in FACTIONS:
        payloads.append({"type": "faction", "name": name, "aliases": [], "audience_known": True})
    for i, name in enumerate(ITEMS):
        payloads.append({
            "type": "item", "name": name, "aliases": [], "audience_known": False,
            "properties": {"seen_by": rand_chars(1 + i % 2)},
        })
    for name in LOCATIONS:
        payloads.append({"type": "location", "name": name, "aliases": [], "audience_known": True})
    for i in range(1, 81):
        payloads.append({
            "type": "event",
            "name": f"{pick(['夜袭', '密会', '失踪', '寻宝', '谈判', '突袭', '布局', '反杀'], i)}·第{i}夜",
            "aliases": [],
            "audience_known": i % 3 != 0,
            "properties": {"known_by": rand_chars(1 + i % 3), "date": f"第{i}夜"},
        })
    for name in CONCEPTS:
        payloads.append({"type": "concept", "name": name, "aliases": [], "audience_known": True})

    ids = {"character": char_ids}
    created = _parallel(lambda p: api.post("/api/entities", p)["id"], payloads, workers)
    for p, pid in zip(payloads, created):
        ids.setdefault(p["type"], []).append(pid)

    rels = []
    for i in range(15):
        rels.append({"source": char_ids[i], "target": char_ids[i + 1], "type": "ALLY", "audience_known": True})
    for i in range(10):
        rels.append({"source": char_ids[i], "target": char_ids[(i + 7) % 20], "type": "RIVAL", "audience_known": False})
    for i, cid in enumerate(char_ids):
        rels.append({"source": cid, "target": ids["faction"][i % 6], "type": "BELONGS_TO", "audience_known": True})
        rels.append({"source": cid, "target": ids["location"][i], "type": "LIVES_IN", "audience_known": True})
        rels.append({"source": cid, "target": ids["item"][i], "type": "OWNS", "audience_known": False})
    for i in range(60):
        rels.append({"source": char_ids[i % 20], "target": ids["event"][i], "type": "PARTICIPATES", "audience_known": True})
    for i in range(15):
        rels.append({"source": ids["event"][i], "target": ids["event"][i + 1], "type": "FOLLOWS", "audience_known": True})
    for i in range(30):
        rels.append({"source": ids["concept"][i], "target": ids["event"][i * 2], "type": "REFLECTS", "audience_known": True})
    for i, fid in enumerate(ids["faction"]):
        rels.append({"source": fid, "target": ids["location"][10 + i], "type": "BASED_AT", "audience_known": True})
    for i in range(12):
        rels.append({"source": char_ids[(i + 5) % 20], "target": ids["skill"][i % 8], "type": "MASTERS", "audience_known": True})

    _parallel(lambda r: api.post("/api/relations", r), rels, workers)

    total = sum(len(v) for v in ids.values())
    print(f"播种完成: {total} 实体 / {len(rels)} 关系 → {api.base}")


if __name__ == "__main__":
    main()
