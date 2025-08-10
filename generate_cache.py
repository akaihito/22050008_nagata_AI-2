import asyncio
import aiohttp
import json
import os
import pandas as pd

DATA_DIR = "data"
POKEAPI_BASE = "https://pokeapi.co/api/v2"

# 🔁 リトライ付き JSON取得関数
async def fetch_json(session, url, retries=3):
    for attempt in range(retries):
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    print(f"Failed to fetch {url}: status {resp.status}")
                    return None
        except Exception as e:
            print(f"Error fetching {url} (attempt {attempt+1}/{retries}): {e}")
            await asyncio.sleep(1)
    return None

# ✅ 安全な進化条件抽出関数
def extract_evolution_condition_from_chain(chain_data, target_name, item_map):
    def search(chain):
        for evo in chain.get("evolves_to", []):
            species_name = evo.get("species", {}).get("name")
            if species_name == target_name:
                for detail in evo.get("evolution_details", []):
                    item_data = detail.get("item")
                    item = item_data.get("name") if item_data else None
                    trigger_data = detail.get("trigger")
                    trigger = trigger_data.get("name") if trigger_data else None
                    level = detail.get("min_level")

                    if item:
                        return f"{item_map.get(item, item)}を使う"
                    elif level:
                        return f"Lv{level}で進化"
                    elif trigger:
                        return f"{trigger}で進化"
                    else:
                        return "進化条件不明"

            result = search(evo)
            if result:
                return result
        return "進化条件不明"

    return search(chain_data.get("chain", {}))

async def extract_form_info(session, form_detail, item_map, evolution_chain):
    form_name_en = form_detail["name"]
    form_species_url = form_detail.get("species", {}).get("url")
    form_species_data = await fetch_json(session, form_species_url) if form_species_url else None

    form_name_ja = next(
        (n["name"] for n in form_species_data.get("names", []) if n["language"]["name"] == "ja-Hrkt"),
        form_name_en
    ) if form_species_data else form_name_en

    form_label = next(
        (n["name"] for n in form_species_data.get("form_names", []) if n["language"]["name"] == "ja-Hrkt"),
        ""
    ) if form_species_data else ""

    is_mega = form_detail.get("is_mega", False)
    if is_mega and not form_label:
        form_label = "メガのすがた"

    image_url = form_detail["sprites"]["other"]["official-artwork"]["front_default"] or form_detail["sprites"]["front_default"]

    evolution_condition = ""
    if evolution_chain:
        evolution_condition = extract_evolution_condition_from_chain(evolution_chain, form_name_en, item_map)

    return {
        "name_en": form_name_en,
        "name_ja": form_name_ja,
        "img": image_url,
        "form_label": form_label,
        "is_mega": is_mega,
        "evolution_condition": evolution_condition
    }

async def fetch_pokemon(session, pokemon_id, item_map):
    url = f"{POKEAPI_BASE}/pokemon/{pokemon_id}"
    data = await fetch_json(session, url)
    if not data:
        return None

    name_en = data["name"]
    types = [t["type"]["name"] for t in data["types"]]
    img = data["sprites"]["other"]["official-artwork"]["front_default"] or data["sprites"]["front_default"]

    species_url = data["species"]["url"]
    species_data = await fetch_json(session, species_url)
    name_ja = None
    evolution_chain_url = None
    forms_data = []
    evolution_chain = None

    if species_data:
        for n in species_data.get("names", []):
            if n["language"]["name"] == "ja-Hrkt":
                name_ja = n["name"]
                break

        evolution_chain_url = species_data.get("evolution_chain", {}).get("url")
        evolution_chain = await fetch_json(session, evolution_chain_url) if evolution_chain_url else None

        for variety in species_data.get("varieties", []):
            form_url = variety["pokemon"]["url"]
            form_detail = await fetch_json(session, form_url)
            if form_detail:
                form_info = await extract_form_info(session, form_detail, item_map, evolution_chain)
                forms_data.append(form_info)

    return {
        "図鑑番号": data["id"],
        "英語名": name_en,
        "日本語名": name_ja or name_en,
        "タイプ": types,
        "画像": img,
        "進化チェーン": evolution_chain,
        "フォルム一覧": forms_data
    }

async def fetch_pokemon_moves(session, pokemon_name, version_map):
    url = f"{POKEAPI_BASE}/pokemon/{pokemon_name}"
    data = await fetch_json(session, url)
    if not data:
        return []

    moves_list = []
    for m in data.get("moves", []):
        move_name_en = m["move"]["name"]
        move_url = m["move"]["url"]
        move_data = await fetch_json(session, move_url)
        move_name_ja = next(
            (n["name"] for n in move_data.get("names", []) if n["language"]["name"] == "ja-Hrkt"),
            move_name_en
        )

        for version_detail in m.get("version_group_details", []):
            version_en = version_detail["version_group"]["name"]
            version_ja = version_map.get(version_en, version_en)
            level_learned = version_detail["level_learned_at"]
            learn_method_en = version_detail["move_learn_method"]["name"]
            moves_list.append({
                "ポケモン": pokemon_name,
                "技名": move_name_en,
                "技名_日本語": move_name_ja,
                "バージョン": version_ja,
                "習得レベル": level_learned,
                "習得方法": learn_method_en
            })
    return moves_list

async def fetch_all_items(session):
    url = f"{POKEAPI_BASE}/item?limit=10000"
    data = await fetch_json(session, url)
    if not data:
        return {}

    item_map = {}
    for item in data["results"]:
        item_data = await fetch_json(session, item["url"])
        if not item_data:
            continue
        name_en = item_data["name"]
        name_ja = next(
            (n["name"] for n in item_data.get("names", []) if n["language"]["name"] == "ja-Hrkt"),
            name_en
        )
        item_map[name_en] = name_ja
    return item_map

async def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    async with aiohttp.ClientSession() as session:
        print("もちもの名取得中...")
        item_map = await fetch_all_items(session)

        print("バージョングループ名読み込み中...")
        version_path = os.path.join(DATA_DIR, "version_group_names.json")
        with open(version_path, "r", encoding="utf-8") as f:
            version_map = json.load(f)

        print("ポケモン情報取得開始...")
        pokemon_tasks = [fetch_pokemon(session, i, item_map) for i in range(1, 1026)]
        pokemon_list = []
        for i, task in enumerate(asyncio.as_completed(pokemon_tasks), 1):
            res = await task
            if res:
                pokemon_list.append(res)
            print(f"\r取得中: {i}/{len(pokemon_tasks)}", end="")
        print("\nポケモン情報取得完了。")

        pokemon_list_sorted = sorted(pokemon_list, key=lambda x: x["図鑑番号"])
        with open(os.path.join(DATA_DIR, "pokemon_cache.json"), "w", encoding="utf-8") as f:
            json.dump(pokemon_list_sorted, f, ensure_ascii=False, indent=2)

        print("技情報取得開始...")
        moves_all = []
        for p in pokemon_list_sorted:
            moves = await fetch_pokemon_moves(session, p["英語名"], version_map)
            moves_all.extend(moves)
            print(f"\r技取得中: {p['英語名']}", end="")
        print("\n技情報取得完了。")

        df = pd.DataFrame(moves_all)
        df.to_csv(os.path.join(DATA_DIR, "moves_cache.csv"), index=False, encoding="utf-8-sig")

        with open(os.path.join(DATA_DIR, "move_names.json"), "w", encoding="utf-8") as f:
            json.dump({row["技名"]: row["技名_日本語"] for row in moves_all}, f, ensure_ascii=False, indent=2)

        with open(os.path.join(DATA_DIR, "item_names.json"), "w", encoding="utf-8") as f:
            json.dump(item_map, f, ensure_ascii=False, indent=2)

        # version_map は既に読み込んだものを再保存（必要なら）
        with open(os.path.join(DATA_DIR, "version_group_names.json"), "w", encoding="utf-8") as f:
            json.dump(version_map, f, ensure_ascii=False, indent=2)

        print("✅ すべてのキャッシュ保存が完了しました！")

if __name__ == "__main__":
    asyncio.run(main())