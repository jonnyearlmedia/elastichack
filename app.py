"""Next Man Up — AI Injury Replacement Scout.

Run:  streamlit run app.py
"""
import streamlit as st

from scout_engine import find_replacements, generate_report, get_player, list_players

st.set_page_config(page_title="Next Man Up", page_icon="⚽", layout="centered")

st.title("⚽ Next Man Up")
st.caption("A star goes down. Elastic finds the closest playing style. "
           "AWS Bedrock writes the scouting report.")

with st.spinner("Loading squad…"):
    try:
        players = list_players(size=500)
    except Exception as e:  # noqa: BLE001
        st.error(f"Can't reach Elasticsearch. Did you run ingest.py and set .env? ({e})")
        st.stop()

names = sorted({p["name"] for p in players if p.get("name")})
if not names:
    st.warning("No players indexed yet. Run:  python ingest.py")
    st.stop()

injured_name = st.selectbox("Who just got injured?", names)

if st.button("Find the replacement", type="primary"):
    injured = get_player(injured_name)
    if not injured:
        st.error("Player not found.")
        st.stop()

    st.subheader(f"🚑 Out: {injured['name']}")
    st.write(injured.get("scouting_text", ""))

    with st.spinner("Elastic searching by playing style…"):
        candidates = find_replacements(injured, k=3)

    if not candidates:
        st.warning("No same-position replacements found in the pool.")
        st.stop()

    st.subheader("🎯 Closest replacements (by vector similarity)")
    for i, c in enumerate(candidates, 1):
        with st.container(border=True):
            st.markdown(f"**{i}. {c['name']}** · {c.get('team','?')} · "
                        f"_{c.get('position','')}_  \n"
                        f"similarity score: `{c['_score']:.3f}`")
            st.caption(c.get("scouting_text", ""))

    with st.spinner("AWS Bedrock writing the scouting report…"):
        report = generate_report(injured, candidates)

    st.subheader("📝 Scout's report (AWS Bedrock via EIS)")
    st.markdown(report)

    st.info("💡 A keyword database can't answer *'similar playing style'* — there's "
            "no keyword for it. Elastic found these on the **vector**, and this "
            "report was written by a model on **AWS Bedrock**. Both sponsors, one loop.")
