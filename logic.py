import json
import pandas as pd
import os
from functools import lru_cache

DATA_DIR = "data"

# 🔽 キャッシュ読み込み関数群
@lru_cache(maxsize=None)
def load_pokemon_cache():
    path = os.path.join(DATA_DIR, "pokemon_cache.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

@lru_cache(maxsize=None)
def load_moves_cache():
    path = os.path.join(DATA_DIR, "moves_cache.csv")
    return pd.read_csv(path, encoding="utf-8-sig")

@lru_cache(maxsize=None)
def load_item_name_map():
    path = os.path.join(DATA_DIR, "item_names.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

@lru_cache(maxsize=None)
def load_version_group_map():
    path = os.path.join(DATA_DIR, "version_group_names.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

@lru_cache(maxsize=None)
def load_type_name_map():
    path = os.path.join(DATA_DIR, "type_names.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

@lru_cache(maxsize=None)
def load_move_name_map():
    path = os.path.join(DATA_DIR, "move_names.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

# 🔽 翻訳補助関数
def safe_translate(name, mapping):
    return mapping.get(name, name)

# 🔽 習得方法マップ
def get_method_map(lang):
    return {
        "level-up": "レベルアップ" if lang == "日本語" else "Level Up",
        "machine": "わざマシン" if lang == "日本語" else "TM",
        "tutor": "教え技" if lang == "日本語" else "Tutor",
        "egg": "遺伝" if lang == "日本語" else "Egg"
    }

# 🔽 ポケモン検索（修正済み：3引数対応）
def get_pokemon_by_name_or_id(query, lang, cache):
    q = query.strip().lower()
    for e in cache.values():
        if str(e["図鑑番号"]) == q or e["英語名"].lower() == q:
            return _make_entry(e, lang)
        if lang == "日本語" and e["日本語名"].lower() == q:
            return _make_entry(e, lang)
    return None

# 🔽 表示用エントリ整形
def _make_entry(entry, lang):
    type_map = load_type_name_map()
    translated_types = translate_types(entry["タイプ"], lang, type_map)

    return {
        "id": entry["図鑑番号"],
        "name_en": entry["英語名"],
        "name": entry["日本語名"] if lang == "日本語" else entry["英語名"],
        "types": translated_types,
        "img": entry["画像"],
        "evolution_chain": entry["進化チェーン"],
        "フォルム一覧": entry.get("フォルム一覧", [])
    }

# 🔽 タイプ翻訳
def translate_types(types, lang, type_map):
    if lang == "日本語":
        return [safe_translate(t, type_map) for t in types]
    return types

# 🔽 進化条件の整形
def format_evolution_conditions(details, lang):
    item_map = load_item_name_map()
    if not details:
        return "条件不明" if lang == "日本語" else "Unknown condition"

    texts = []
    for d in details:
        trig = d.get("trigger", {}).get("name", "")
        lvl  = d.get("min_level")
        itm  = d.get("item", {}).get("name") if d.get("item") else None
        hp   = d.get("min_happiness")
        tm   = d.get("time_of_day")
        mv   = d.get("known_move", {}).get("name") if d.get("known_move") else None

        if lang == "日本語":
            if trig == "level-up" and lvl:
                texts.append(f"{lvl}レベルで進化")
            elif trig == "use-item" and itm:
                texts.append(f"{safe_translate(itm, item_map)}を使う")
            elif hp:
                texts.append("なつき度が高い状態で進化")
            elif mv:
                texts.append(f"{mv}を覚えていると進化")
            elif tm:
                texts.append(f"{tm}に進化")
            else:
                texts.append("特殊な条件で進化")
        else:
            if trig == "level-up" and lvl:
                texts.append(f"Evolves at level {lvl}")
            elif trig == "use-item" and itm:
                texts.append(f"Use {itm} to evolve")
            elif hp:
                texts.append("High friendship required")
            elif mv:
                texts.append(f"Knows move {mv}")
            elif tm:
                texts.append(f"Evolves during {tm}")
            else:
                texts.append("Special condition")

    return "、".join(texts) if lang == "日本語" else "; ".join(texts)

# 🔽 進化ツリー構築
def get_evolution_tree(base_en, lang, cache_dict, item_map):
    tree = []
    root = cache_dict.get(base_en)
    if not root:
        return tree

    chain = root["進化チェーン"].get("chain", {})

    def traverse(node, cond=""):
        name_en = node["species"]["name"]
        entry = cache_dict.get(name_en)
        if not entry:
            return

        tree.append({
            "name": entry["日本語名"] if lang == "日本語" else entry["英語名"],
            "name_en": name_en,
            "id": entry["図鑑番号"],
            "img": entry["画像"],
            "types": translate_types(entry["タイプ"], lang, load_type_name_map()),
            "condition": cond or ("条件不明" if lang == "日本語" else "Unknown condition")
        })

        for evo in node.get("evolves_to", []):
            next_cond = format_evolution_conditions(evo.get("evolution_details", []), lang)
            traverse(evo, next_cond)

    traverse(chain)
    return tree

# 🔽 技一覧取得（言語対応・翻訳付き）
def get_moves_for_pokemon(name_en, lang, moves_df, version_group_map, move_name_map=None):
    df = moves_df[moves_df["ポケモン"] == name_en].copy()
    if df.empty:
        cols = (
            ["ポケモン", "技名", "バージョン", "習得レベル", "習得方法"]
            if lang == "日本語"
            else ["Pokemon", "Move", "Version", "Level", "Method"]
        )
        return pd.DataFrame(columns=cols)

    df["バージョン"] = df["バージョン"].map(lambda x: safe_translate(x, version_group_map))
    method_map = get_method_map(lang)

    if lang == "日本語":
        df["習得方法"] = df["習得方法"].map(lambda x: safe_translate(x, method_map))
        if move_name_map:
            df["技名"] = df["技名"].map(lambda x: safe_translate(x, move_name_map))
        df = df[["ポケモン", "技名", "バージョン", "習得レベル", "習得方法"]]
    else:
        df["習得方法"] = df["習得方法"].map(lambda x: safe_translate(x, method_map))
        df = df.rename(columns={
            "ポケモン": "Pokemon",
            "技名": "Move",
            "バージョン": "Version",
            "習得レベル": "Level",
            "習得方法": "Method"
        })

    sortcol = "習得レベル" if lang == "日本語" else "Level"
    return df.sort_values(by=sortcol).reset_index(drop=True)