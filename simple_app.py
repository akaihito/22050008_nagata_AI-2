import streamlit as st
import pandas as pd
import json
import os
from logic import (
    load_pokemon_cache,
    load_moves_cache,
    load_item_name_map,
    load_version_group_map,
    load_type_name_map,
    get_pokemon_by_name_or_id,
    get_evolution_tree,
    get_moves_for_pokemon
)

# ページ設定
st.set_page_config(page_title="ポケモン進化ツリー表示", layout="wide")
st.markdown("<h1 style='font-size:40px;'>🌱 ポケモン進化ツリー表示アプリ</h1>", unsafe_allow_html=True)

# データ読み込み関数
@st.cache_data
def load_pokemon_data():
    raw_data = load_pokemon_cache()
    return {entry["英語名"]: entry for entry in raw_data}

@st.cache_data
def load_move_name_map():
    path = os.path.join("data", "move_names.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

# データ読み込み
pokemon_data   = load_pokemon_data()
moves_data     = load_moves_cache()
item_map       = load_item_name_map()
version_map    = load_version_group_map()
type_name_map  = load_type_name_map()
move_name_map  = load_move_name_map()

# 表示言語選択
lang = st.selectbox("表示言語を選択", ["日本語", "English"])

# 検索フォーム
with st.form("search_form", clear_on_submit=False):
    user_input = st.text_input("ポケモン名またはIDを入力（例：ピカチュウ / Eevee / 25）")
    version_col = "バージョン" if lang == "日本語" else "Version"
    all_versions = moves_data["バージョン"].unique() if not moves_data.empty else []
    version_labels = sorted({ version_map.get(v, v) for v in all_versions })
    version_filter = st.selectbox("技のバージョンで絞り込み（任意）", ["すべて"] + version_labels)
    submitted = st.form_submit_button("検索")

# 検索処理
if submitted and user_input:
    entry = get_pokemon_by_name_or_id(user_input, lang, pokemon_data)
    if entry is None:
        st.error("ポケモンが見つかりませんでした。" if lang == "日本語" else "Pokemon not found.")
    else:
        evolution_tree = get_evolution_tree(entry["name_en"], lang, pokemon_data, item_map)

        # 進化ツリー表示
        st.subheader("進化ツリー" if lang == "日本語" else "Evolution Tree")
        for node in evolution_tree:
            col1, col2 = st.columns([1, 2])
            with col1:
                st.image(node["img"], caption=node["name"], width=150)
            with col2:
                translated_types = node["types"]
                info_dict = {
                    ("名前" if lang == "日本語" else "Name"): node["name"],
                    ("英語名" if lang == "日本語" else "English Name"): node["name_en"],
                    ("図鑑番号" if lang == "日本語" else "Dex ID"): node["id"],
                    ("タイプ" if lang == "日本語" else "Type"): ", ".join(translated_types),
                    ("進化条件" if lang == "日本語" else "Evolution Condition"): node["condition"]
                }
                # 🔧 PyArrow型エラー対策：すべて文字列化
                info_dict = {k: str(v) for k, v in info_dict.items()}
                df_info = pd.DataFrame(info_dict.items(), columns=["項目" if lang == "日本語" else "Field", "内容" if lang == "日本語" else "Value"])
                st.dataframe(df_info, use_container_width=True)

            # 技一覧表示
            st.markdown("#### 🌀 覚えられる技一覧" if lang == "日本語" else "#### 🌀 Learnable Moves")
            moves_df = get_moves_for_pokemon(node["name_en"], lang, moves_data, version_map, move_name_map)

            if "ポケモン" in moves_df.columns:
                moves_df["ポケモン"] = moves_df["ポケモン"].map(
                    lambda name_en: pokemon_data.get(name_en, {}).get("日本語名", name_en)
                )

            if version_filter != "すべて" and version_col in moves_df.columns:
                moves_df = moves_df[moves_df[version_col] == version_filter]

            if not moves_df.empty:
                st.dataframe(moves_df, use_container_width=True)
            else:
                st.info("このポケモンは該当バージョンで技を覚えません。" if lang == "日本語" else "No learnable moves found for selected version.")

        # 別フォルム一覧の表示
        forms = entry.get("フォルム一覧", [])
        if forms:
            st.subheader("別フォルム一覧" if lang == "日本語" else "Alternate Forms")
            for form in forms:
                form_name = form["name_ja"] if lang == "日本語" else form["name_en"]
                form_img = form.get("img")
                form_label = form.get("form_label") or ("通常のすがた" if lang == "日本語" else "Default Form")
                evo_cond = form.get("evolution_condition") or ("条件不明" if lang == "日本語" else "Unknown condition")

                col1, col2 = st.columns([1, 4])
                with col1:
                    if form_img:
                        st.image(form_img, width=100)
                with col2:
                    st.markdown(f"**{form_name}**")
                    st.caption(form_label)
                    st.caption(f"進化条件: {evo_cond}")

elif submitted:
    st.warning("検索ワードを入力してください。" if lang == "日本語" else "Please enter a search term.")