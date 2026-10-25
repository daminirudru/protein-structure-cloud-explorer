
%%writefile app.py
import os
import json
import tempfile
import streamlit as st
import boto3
import streamlit.components.v1 as components
from Bio.PDB import PDBParser

st.set_page_config(page_title="Protein Cloud Explorer", page_icon="🧬", layout="wide")
st.title("🧬 Protein Structure Cloud Explorer")
st.caption("Amazon S3 • Protein structure storage • Interactive 3D visualization")

BUCKET = "protein-structure-project-2026-honey123"
REGION = "eu-north-1"

@st.cache_resource
def get_s3():
    return boto3.client(
        "s3",
        region_name=REGION,
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
    )

try:
    s3 = get_s3()
    result = s3.list_objects_v2(Bucket=BUCKET, Prefix="protein-structures/")
    pdb_files = [
        item["Key"] for item in result.get("Contents", [])
        if item["Key"].lower().endswith(".pdb")
    ]
except Exception as e:
    st.error(f"Could not access S3: {type(e).__name__}: {e}")
    st.stop()

if not pdb_files:
    st.warning("No PDB files found under protein-structures/ in your S3 bucket.")
    st.stop()

selected_key = st.sidebar.selectbox("Select a protein structure", pdb_files)

if st.sidebar.button("Refresh file list"):
    st.cache_data.clear()
    st.rerun()

try:
    response = s3.get_object(Bucket=BUCKET, Key=selected_key)
    pdb_text = response["Body"].read().decode("utf-8", errors="replace")
except Exception as e:
    st.error(f"Could not download PDB: {type(e).__name__}: {e}")
    st.stop()

atom_lines = [
    line for line in pdb_text.splitlines()
    if line.startswith(("ATOM  ", "HETATM"))
]

if not atom_lines:
    st.error("The selected file has no PDB atom-coordinate records.")
    st.stop()

temp_path = None
try:
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".pdb", delete=False
    ) as temp:
        temp.write(pdb_text)
        temp_path = temp.name

    structure = PDBParser(QUIET=True).get_structure("protein", temp_path)
    atoms = list(structure.get_atoms())
    residues = list(structure.get_residues())
finally:
    if temp_path and os.path.exists(temp_path):
        os.remove(temp_path)

col1, col2, col3 = st.columns(3)
col1.metric("Atom records", f"{len(atom_lines):,}")
col2.metric("Parsed atoms", f"{len(atoms):,}")
col3.metric("Residues", f"{len(residues):,}")

st.subheader("Interactive 3D protein structure")
st.write("Drag to rotate and use the mouse wheel or trackpad to zoom.")

pdb_json = json.dumps(pdb_text)
html = f"""
<div id="viewer" style="width:100%;height:500px;"></div>
<script src="https://3Dmol.org/build/3Dmol-min.js"></script>
<script>
const pdbData = {pdb_json};
const element = document.getElementById("viewer");
if (window.$3Dmol) {{
    const viewer = $3Dmol.createViewer(element, {{backgroundColor: "white"}});
    viewer.addModel(pdbData, "pdb");
    viewer.setStyle({{}}, {{cartoon: {{color: "spectrum"}}}});
    viewer.zoomTo();
    viewer.render();
}} else {{
    element.innerHTML = "3D viewer library did not load. Check your internet connection.";
}}
</script>
"""
components.html(html, height=520, scrolling=False)

st.subheader("PDB file details")
st.write(f"**S3 object:** `{selected_key}`")
st.write(f"**File size:** {len(pdb_text.encode('utf-8')):,} bytes")

st.download_button(
    "Download protein structure",
    data=pdb_text.encode("utf-8"),
    file_name=selected_key.split("/")[-1],
    mime="chemical/x-pdb",
)

with st.expander("Preview first 30 PDB lines"):
    st.code("\n".join(pdb_text.splitlines()[:30]), language="text")

st.info(
    "Educational demonstration using a precomputed AlphaFold structure. "
    "AWS S3 stores and retrieves the structure; prediction was not run on AWS."
)
