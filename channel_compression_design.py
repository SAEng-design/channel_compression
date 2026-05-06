import streamlit as st
import pandas as pd
import math

# --- Page config ---
st.set_page_config(
    page_title="Channel Column — Compression Design",
    page_icon="🏛️",
    layout="wide"
)
st.title("Channel Section — Compressive Resistance")
st.caption("Per SANS 10162-1 | Cl. 11 (Classification), 13.3 (Compressive Resistance), 10.4 (Slenderness)")

# --- Load section databases ---
@st.cache_data
def load_sections():
    import os
    local_path = r"W:\Central Information\DESIGN\VIKO Design Tool\Channels"
    pfc_local = os.path.join(local_path, "parallel_flange_channels.csv")
    tfc_local = os.path.join(local_path, "taper_flange_channels.csv")

    if os.path.exists(pfc_local) and os.path.exists(tfc_local):
        pfc = pd.read_csv(pfc_local, sep=";", decimal=",", encoding="utf-8-sig", dtype=str)
        tfc = pd.read_csv(tfc_local, sep=";", decimal=",", encoding="utf-8-sig", dtype=str)
    else:
        pfc = pd.read_csv("parallel_flange_channels.csv", sep=";", decimal=",", encoding="utf-8-sig", dtype=str)
        tfc = pd.read_csv("taper_flange_channels.csv",    sep=";", decimal=",", encoding="utf-8-sig", dtype=str)

    pfc.columns = pfc.columns.str.strip()
    tfc.columns = tfc.columns.str.strip()

    for df in [pfc, tfc]:
        for col in df.columns:
            if col != "designation":
                df[col] = pd.to_numeric(df[col].str.replace(",", "."), errors="coerce")

    return pfc, tfc

pfc_df, tfc_df = load_sections()

# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.header("Section")
section_type = st.sidebar.radio("Section type", ["Parallel Flange Channel (PFC)", "Taper Flange Channel (TFC)"])

if section_type.startswith("Parallel"):
    designations = pfc_df["designation"].tolist()
    df_use       = pfc_df
    is_taper     = False
else:
    designations = tfc_df["designation"].tolist()
    df_use       = tfc_df
    is_taper     = True

selected = st.sidebar.selectbox("Designation", designations)
row = df_use[df_use["designation"] == selected].iloc[0]

# Extract section properties
m   = float(row["m"])
h   = float(row["h"])
b   = float(row["b"])
tw  = float(row["tw"])
tf  = float(row["tf"])
r1  = float(row["r1"])
hw  = float(row["hw"])
A   = float(row["A"]) * 1e3
ac  = float(row["ac"])
ay  = float(row["ay"])
Ix  = float(row["Ixx"]) * 1e6
Zex = float(row["Zex"]) * 1e3
rx  = float(row["rxx"])
Iy  = float(row["Iyy"]) * 1e6
Zey = float(row["Zey"]) * 1e3
ry  = float(row["ryy"])
J   = float(row["J"]) * 1e3
Cw  = float(row["Cw"]) * 1e9

if is_taper:
    b1   = float(row["b1"])
    r2   = float(row["r2"])
    beta = float(row["beta"])
else:
    b1   = b
    r2   = None
    beta = None

xo = ac
yo = 0.0

# ── Materials ─────────────────────────────────────────────────────────────────
st.sidebar.header("Material")
steel_grades = {
    "S355JR — fy = 355 MPa": 355,
    "S275JR — fy = 275 MPa": 275,
    "S235JR — fy = 235 MPa": 235,
    "Custom...": None,
}
grade_label = st.sidebar.selectbox("Steel Grade", list(steel_grades.keys()))

if grade_label == "Custom...":
    fy_nominal = st.sidebar.number_input(
        "Custom fy (MPa)",
        min_value=200,
        max_value=700,
        value=355,
        step=5,
        help="Enter the yield strength of your custom steel grade in MPa"
    )
else:
    fy_nominal = steel_grades[grade_label]

def fy_for_thickness(fy_nom, tf_val):
    """Apply tf > 16 mm reduction per SANS 10025 / SAISC convention."""
    if tf_val > 16:
        if   fy_nom == 355: return 345
        elif fy_nom == 275: return 265
        elif fy_nom == 235: return 225
    return fy_nom

# fy applicable to the currently-selected section
fy = fy_for_thickness(fy_nominal, tf)

E   = 200000
G   = 77000
phi = 0.90

# ── Manufacturing type ────────────────────────────────────────────────────────
st.sidebar.header("Manufacturing")
mfg = st.sidebar.radio(
    "Manufacturing type (sets parameter n)",
    ["Hot-rolled (n = 1.34)", "Welded stress-relieved (n = 2.24)"]
)
n_param = 1.34 if "1.34" in mfg else 2.24

# ── Effective lengths ─────────────────────────────────────────────────────────
st.sidebar.header("Effective Lengths")
st.sidebar.caption("Enter KL values — set to 0 for axes that are laterally restrained")

KLx = st.sidebar.number_input("KLx — about strong axis (mm)",  min_value=0, max_value=20000, value=2000, step=100)
KLy = st.sidebar.number_input("KLy — about weak axis (mm)",    min_value=0, max_value=20000, value=2000, step=100)
KLz = st.sidebar.number_input("KLz — torsional (mm)",           min_value=0, max_value=20000, value=2000, step=100)

# ── Design check ──────────────────────────────────────────────────────────────
st.sidebar.header("Design Check (optional)")
C_f = st.sidebar.number_input("Factored axial load C* (kN)", min_value=0.0, value=0.0, step=10.0)

# ══ CORE CALCULATION FUNCTION ═════════════════════════════════════════════════
def compute_Cr(section_row, is_taper_section, fy_nom, KLx, KLy, KLz, n_param,
               E=200000, G=77000, phi=0.90):
    """Run the full Cr calculation for one section. Mirrors Steps 1–5 of the
    main calc. Used by both the design check tab and the optimiser tab."""

    b_  = float(section_row["b"])
    tw_ = float(section_row["tw"])
    tf_ = float(section_row["tf"])
    hw_ = float(section_row["hw"])
    A_  = float(section_row["A"]) * 1e3
    ac_ = float(section_row["ac"])
    rx_ = float(section_row["rxx"])
    ry_ = float(section_row["ryy"])
    J_  = float(section_row["J"]) * 1e3
    Cw_ = float(section_row["Cw"]) * 1e9

    if is_taper_section:
        b1_ = float(section_row["b1"])
    else:
        b1_ = b_

    xo_, yo_ = ac_, 0.0

    fy_ = fy_for_thickness(fy_nom, tf_)

    # 1. Classification
    flange_outstand_ = b1_ if is_taper_section else b_
    flange_ratio_    = flange_outstand_ / tf_
    flange_limit_    = 200 / math.sqrt(fy_)
    flange_class4    = flange_ratio_ > flange_limit_

    web_ratio_ = hw_ / tw_
    web_limit_ = 670 / math.sqrt(fy_)
    web_class4 = web_ratio_ > web_limit_

    is_class4_ = flange_class4 or web_class4

    # 2. Slenderness
    sl_x_ = KLx / rx_ if KLx > 0 else 0
    sl_y_ = KLy / ry_ if KLy > 0 else 0
    slenderness_ok_ = (KLx == 0 or sl_x_ <= 200) and (KLy == 0 or sl_y_ <= 200)

    # 3. Elastic buckling
    f_ex_ = math.pi**2 * E / (KLx/rx_)**2 if KLx > 0 else float("inf")
    f_ey_ = math.pi**2 * E / (KLy/ry_)**2 if KLy > 0 else float("inf")

    r0_sq_ = xo_**2 + yo_**2 + rx_**2 + ry_**2

    if KLz > 0:
        f_ez_ = (math.pi**2 * E * Cw_ / KLz**2 + G * J_) / (A_ * r0_sq_)
    else:
        f_ez_ = float("inf")

    Omega_ = 1 - (xo_**2 + yo_**2) / r0_sq_

    if KLx > 0 and KLz > 0 and Omega_ > 0:
        inside_sqrt_ = 1 - (4 * f_ex_ * f_ez_ * Omega_) / (f_ex_ + f_ez_)**2
        if inside_sqrt_ < 0:
            inside_sqrt_ = 0
        f_exz_ = ((f_ex_ + f_ez_) / (2 * Omega_)) * (1 - math.sqrt(inside_sqrt_))
    else:
        f_exz_ = float("inf")

    f_e_ = min(f_ey_, f_exz_)

    # 4. Effective area
    lam_for_aef_ = math.sqrt(fy_ / f_e_)
    f_for_aef_   = fy_ * (1 + lam_for_aef_**(2 * n_param))**(-1 / n_param)
    f_for_aef_   = min(f_for_aef_, fy_)

    A_eff_ = A_
    if is_class4_:
        if flange_class4:
            W_f = flange_outstand_ / tf_
            W_lim_f = 0.644 * math.sqrt(0.43 * E / f_for_aef_)
            if W_f > W_lim_f:
                b_eff_f = 0.95 * tf_ * math.sqrt(0.43 * E / f_for_aef_) * (1 - (0.208 / W_f) * math.sqrt(0.43 * E / f_for_aef_))
                A_eff_ -= 2 * (flange_outstand_ - b_eff_f) * tf_

        if web_class4:
            W_w = hw_ / tw_
            W_lim_w = 0.644 * math.sqrt(4.0 * E / f_for_aef_)
            if W_w > W_lim_w:
                b_eff_w = 0.95 * tw_ * math.sqrt(4.0 * E / f_for_aef_) * (1 - (0.208 / W_w) * math.sqrt(4.0 * E / f_for_aef_))
                A_eff_ -= (hw_ - b_eff_w) * tw_

        A_eff_ = max(A_eff_, 0)

    # 5. Cr
    lam_ = math.sqrt(fy_ / f_e_)
    Cr_  = phi * A_eff_ * fy_ * (1 + lam_**(2 * n_param))**(-1 / n_param) / 1000

    return {
        "Cr": Cr_,
        "lam": lam_,
        "fe": f_e_,
        "fex": f_ex_, "fey": f_ey_, "fez": f_ez_, "fexz": f_exz_,
        "Omega": Omega_,
        "is_class4": is_class4_,
        "flange_class4": flange_class4,
        "web_class4": web_class4,
        "flange_ratio": flange_ratio_, "flange_limit": flange_limit_,
        "web_ratio": web_ratio_, "web_limit": web_limit_,
        "sl_x": sl_x_, "sl_y": sl_y_,
        "slenderness_ok": slenderness_ok_,
        "A": A_, "A_eff": A_eff_,
        "f_for_aef": f_for_aef_,
        "fy": fy_,
        "r0_sq": r0_sq_,
        "xo": xo_, "yo": yo_,
        "flange_outstand": flange_outstand_,
    }

# Run the calc for the currently-selected section
res = compute_Cr(row, is_taper, fy_nominal, KLx, KLy, KLz, n_param)
Cr           = res["Cr"]
lam          = res["lam"]
f_e          = res["fe"]
f_ex, f_ey   = res["fex"], res["fey"]
f_ez, f_exz  = res["fez"], res["fexz"]
Omega        = res["Omega"]
is_class4    = res["is_class4"]
A_eff        = res["A_eff"]
f_for_aef    = res["f_for_aef"]
sl_x, sl_y   = res["sl_x"], res["sl_y"]
sl_x_ok      = sl_x <= 200
sl_y_ok      = sl_y <= 200
flange_ratio = res["flange_ratio"]
flange_limit = res["flange_limit"]
web_ratio    = res["web_ratio"]
web_limit    = res["web_limit"]

flange_class = "Class 4 (slender)" if res["flange_class4"] else "Not Class 4"
web_class    = "Class 4 (slender)" if res["web_class4"]    else "Not Class 4"
section_class = "Class 4 (Slender)" if is_class4 else "Class 3 or better"

if   abs(f_e - f_ey)  < 1e-6: governing_mode = "Flexural buckling about y-axis"
else:                          governing_mode = "Flexural-torsional buckling (x-axis + torsion)"

# ══ TABS ══════════════════════════════════════════════════════════════════════

tab_check, tab_optim = st.tabs(["📋 Design Check", "🎯 Section Optimiser"])

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — DESIGN CHECK
# ─────────────────────────────────────────────────────────────────────────────
with tab_check:
    st.subheader("Section properties")
    props = {
        "Designation":   selected,
        "Section type":  "PFC" if not is_taper else "TFC",
        "Mass m":        f"{m:.1f} kg/m",
        "Depth h":       f"{h:.1f} mm",
        "Width b":       f"{b:.1f} mm",
        "tw":            f"{tw:.1f} mm",
        "tf":            f"{tf:.1f} mm",
        "Web depth hw":  f"{hw:.1f} mm",
        "A (gross)":     f"{A:.0f} mm²",
        "Ix":            f"{Ix:.2e} mm⁴",
        "Iy":            f"{Iy:.2e} mm⁴",
        "rx":            f"{rx:.1f} mm",
        "ry":            f"{ry:.1f} mm",
        "J":             f"{J:.2e} mm⁴",
        "Cw":            f"{Cw:.2e} mm⁶",
        "ac (xo)":       f"{ac:.1f} mm",
        "fy (used)":     f"{fy} MPa",
    }
    if is_taper:
        props["b₁ (flat)"] = f"{b1:.1f} mm"
        props["β (taper)"] = f"{beta:.2f}°"

    cols = st.columns(4)
    for i, (k, v) in enumerate(props.items()):
        cols[i % 4].markdown(f"**{k}:** {v}")

    st.divider()

    if C_f > 0:
        util   = C_f / Cr
        status = "✅ PASS" if Cr >= C_f else "❌ FAIL"
        header = (
            f"**Compressive resistance Cr = {Cr:.1f} kN**  |  "
            f"Governing: {governing_mode}  |  "
            f"C* = {C_f:.1f} kN  |  "
            f"Utilisation = {util:.2f}  |  {status}"
        )
    else:
        header = (
            f"**Compressive resistance Cr = {Cr:.1f} kN**  |  "
            f"Governing: {governing_mode}"
        )

    st.subheader("Design results")

    with st.expander(header, expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Cr",            f"{Cr:.1f} kN")
        c2.metric("λ",             f"{lam:.3f}")
        c3.metric("f_e",           f"{f_e:.1f} MPa")
        c4.metric("Section class", "Class 4" if is_class4 else "Cl. 3 or better")

        flange_label = "Flange b₁/tf (outstand of flat portion)" if is_taper else "Flange b/tf (outstand)"

        rows = [
            ("─── 1. Section classification — Cl. 11 ───",                           ""),
            (flange_label,                                                           f"{flange_ratio:.2f}"),
            ("Flange limit (200/√fy)",                                               f"{flange_limit:.2f}"),
            ("Flange",                                                               flange_class),
            ("Web hw/tw",                                                            f"{web_ratio:.2f}"),
            ("Web limit (670/√fy)",                                                  f"{web_limit:.2f}"),
            ("Web",                                                                  web_class),
            ("Overall section",                                                      section_class),

            ("─── 2. Slenderness check — Cl. 10.4.2.1 ───",                          ""),
            ("KLx / rx",                                                             f"{sl_x:.1f}" if KLx > 0 else "— (laterally restrained)"),
            ("KLy / ry",                                                             f"{sl_y:.1f}" if KLy > 0 else "— (laterally restrained)"),
            ("Limit",                                                                "200"),
            ("KLx/rx status",                                                        "OK ✅" if (KLx == 0 or sl_x_ok) else "EXCEEDS LIMIT ❌"),
            ("KLy/ry status",                                                        "OK ✅" if (KLy == 0 or sl_y_ok) else "EXCEEDS LIMIT ❌"),

            ("─── 3. Elastic buckling stresses — Cl. 13.3.2 ───",                    ""),
            ("xo (= ac, shear centre offset)",                                       f"{xo:.1f} mm"),
            ("yo",                                                                   f"{yo:.1f} mm"),
            ("r₀² = xo² + yo² + rx² + ry²",                                          f"{res['r0_sq']:.0f} mm²"),
            ("f_ex = π²E / (KLx/rx)²",                                               f"{f_ex:.1f} MPa" if KLx > 0 else "— (restrained)"),
            ("f_ey = π²E / (KLy/ry)²",                                               f"{f_ey:.1f} MPa" if KLy > 0 else "— (restrained)"),
            ("f_ez = [π²E·Cw/(KLz)² + GJ] / (A·r₀²)",                                f"{f_ez:.1f} MPa" if KLz > 0 else "— (restrained)"),
            ("Ω = 1 - (xo² + yo²)/r₀²",                                              f"{Omega:.3f}"),
            ("f_exz (flexural-torsional, Cl. 13.3.2(b))",                            f"{f_exz:.1f} MPa" if (KLx > 0 and KLz > 0) else "— (restrained)"),
            ("Governing f_e = min(f_ey, f_exz)",                                     f"{f_e:.1f} MPa"),
            ("Governing mode",                                                       governing_mode),

            ("─── 4. Effective area — Cl. 13.3.3 ───",                               ""),
            ("f used = fy·(1+λ²ⁿ)^(-1/n), capped at fy",                             f"{f_for_aef:.1f} MPa"),
            ("A (gross)",                                                            f"{A:.0f} mm²"),
            ("A_eff (used in Cr)",                                                   f"{A_eff:.0f} mm²"),
            ("Area reduction",                                                       f"{(1 - A_eff/A)*100:.1f} %"),

            ("─── 5. Compressive resistance — Cl. 13.3.1 / Eq. 4.24 ───",            ""),
            ("Manufacturing parameter n",                                            f"{n_param}"),
            ("λ = √(fy/f_e)",                                                        f"{lam:.3f}"),
            ("Resistance factor φ",                                                  f"{phi}"),
            ("Cr = φ·A_eff·fy·(1 + λ^(2n))^(-1/n)",                                  f"{Cr:.1f} kN"),
        ]

        df_out = pd.DataFrame(rows, columns=["Parameter", "Value"])
        st.dataframe(df_out, use_container_width=True, hide_index=True)

    st.subheader("Buckling mode comparison")
    mode_rows = []
    for label, fe_val, KL_val in [
        ("Flexural about x-axis (informational)", f_ex,  KLx),
        ("Flexural about y-axis",                 f_ey,  KLy),
        ("Pure torsional about z-axis",           f_ez,  KLz),
        ("Flexural-torsional (x + z)",            f_exz, KLx if KLx > 0 and KLz > 0 else 0),
    ]:
        if KL_val == 0:
            Cr_mode = "—"
            marker  = ""
        else:
            lam_mode  = math.sqrt(fy / fe_val)
            Cr_mode_v = phi * A_eff * fy * (1 + lam_mode**(2 * n_param))**(-1 / n_param) / 1000
            Cr_mode   = f"{Cr_mode_v:.1f}"
            marker    = "★ " if abs(fe_val - f_e) < 0.01 else ""
        mode_rows.append({
            "Buckling mode":         marker + label,
            "f_e (MPa)":              f"{fe_val:.1f}" if KL_val > 0 else "—",
            "Cr if this governed (kN)": Cr_mode,
        })
    st.dataframe(pd.DataFrame(mode_rows), use_container_width=True, hide_index=True)

    st.caption(
        "Note: For singly-symmetric channels (symmetric about x-axis), the governing elastic "
        "buckling stress is the minimum of f_ey (weak-axis flexural) and f_exz (flexural-torsional, "
        "which combines x-axis flexure with torsion via Ω). Pure flexural buckling about the strong "
        "axis (f_ex) does not govern alone — it is coupled with torsion in f_exz."
    )

# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — OPTIMISER
# ─────────────────────────────────────────────────────────────────────────────
with tab_optim:
    st.subheader("Section Optimiser")
    st.caption(
        "Finds the lightest passing PFC and TFC for the given factored load C* and "
        "the effective lengths, steel grade, and manufacturing type set in the sidebar."
    )

    Cu_target = st.number_input(
        "Target factored compressive load C* (kN)",
        min_value=0.0, value=max(C_f, 100.0), step=10.0,
        help="The optimiser will find the lightest section where Cr ≥ C*."
    )

    st.markdown(
        f"**Inputs from sidebar:** Steel grade fy = {fy_nominal} MPa (nominal) | "
        f"Manufacturing n = {n_param} | "
        f"KLx = {KLx} mm | KLy = {KLy} mm | KLz = {KLz} mm"
    )

    if Cu_target <= 0:
        st.info("Enter a target C* greater than 0 to run the optimiser.")
    else:
        def evaluate_family(df, is_taper_family):
            results = []
            for _, srow in df.iterrows():
                try:
                    r = compute_Cr(srow, is_taper_family, fy_nominal, KLx, KLy, KLz, n_param)
                    results.append({
                        "designation": srow["designation"],
                        "mass":        float(srow["m"]),
                        "Cr":          r["Cr"],
                        "passes":      (r["Cr"] >= Cu_target) and r["slenderness_ok"],
                        "slenderness_ok": r["slenderness_ok"],
                        "is_class4":   r["is_class4"],
                        "governing":   "FT" if abs(r["fe"] - r["fexz"]) < 0.01 else "Fy",
                        "util":        Cu_target / r["Cr"] if r["Cr"] > 0 else float("inf"),
                    })
                except Exception:
                    pass
            return pd.DataFrame(results)

        pfc_results = evaluate_family(pfc_df, False)
        tfc_results = evaluate_family(tfc_df, True)

        def lightest_passing(df_results):
            passing = df_results[df_results["passes"]].sort_values("mass")
            if len(passing) == 0:
                return None
            return passing.iloc[0]

        best_pfc = lightest_passing(pfc_results)
        best_tfc = lightest_passing(tfc_results)

        st.divider()

        col_pfc, col_tfc = st.columns(2)

        with col_pfc:
            st.markdown("### 🔵 Lightest Parallel Flange Channel (PFC)")
            if best_pfc is None:
                st.error("❌ No PFC in the database satisfies C\\* with the given KL values.")
                heaviest = pfc_results.sort_values("mass").iloc[-1]
                st.caption(
                    f"For reference, the heaviest PFC ({heaviest['designation']}, "
                    f"{heaviest['mass']:.1f} kg/m) gives Cr = {heaviest['Cr']:.1f} kN — "
                    f"still {(Cu_target - heaviest['Cr']):.1f} kN short of C*."
                )
            else:
                st.metric("Designation", best_pfc["designation"])
                c1, c2, c3 = st.columns(3)
                c1.metric("Mass",  f"{best_pfc['mass']:.1f} kg/m")
                c2.metric("Cr",    f"{best_pfc['Cr']:.1f} kN")
                c3.metric("Util.", f"{best_pfc['util']:.2f}")
                tags = []
                tags.append(f"Governing: {'Flex-Tors' if best_pfc['governing'] == 'FT' else 'Weak-axis flex'}")
                if best_pfc["is_class4"]:
                    tags.append("⚠ Class 4 — A_eff reduced")
                st.caption(" | ".join(tags))

        with col_tfc:
            st.markdown("### 🟢 Lightest Taper Flange Channel (TFC)")
            if best_tfc is None:
                st.error("❌ No TFC in the database satisfies C\\* with the given KL values.")
                heaviest = tfc_results.sort_values("mass").iloc[-1]
                st.caption(
                    f"For reference, the heaviest TFC ({heaviest['designation']}, "
                    f"{heaviest['mass']:.1f} kg/m) gives Cr = {heaviest['Cr']:.1f} kN — "
                    f"still {(Cu_target - heaviest['Cr']):.1f} kN short of C*."
                )
            else:
                st.metric("Designation", best_tfc["designation"])
                c1, c2, c3 = st.columns(3)
                c1.metric("Mass",  f"{best_tfc['mass']:.1f} kg/m")
                c2.metric("Cr",    f"{best_tfc['Cr']:.1f} kN")
                c3.metric("Util.", f"{best_tfc['util']:.2f}")
                tags = []
                tags.append(f"Governing: {'Flex-Tors' if best_tfc['governing'] == 'FT' else 'Weak-axis flex'}")
                if best_tfc["is_class4"]:
                    tags.append("⚠ Class 4 — A_eff reduced")
                st.caption(" | ".join(tags))

        st.divider()

        if best_pfc is not None and best_tfc is not None:
            if best_pfc["mass"] < best_tfc["mass"]:
                st.success(
                    f"💡 **Lightest overall: {best_pfc['designation']} (PFC)** at "
                    f"{best_pfc['mass']:.1f} kg/m — saves "
                    f"{best_tfc['mass'] - best_pfc['mass']:.1f} kg/m vs the lightest TFC."
                )
            elif best_tfc["mass"] < best_pfc["mass"]:
                st.success(
                    f"💡 **Lightest overall: {best_tfc['designation']} (TFC)** at "
                    f"{best_tfc['mass']:.1f} kg/m — saves "
                    f"{best_pfc['mass'] - best_tfc['mass']:.1f} kg/m vs the lightest PFC."
                )
            else:
                st.success(
                    f"💡 PFC and TFC options are equal in mass ({best_pfc['mass']:.1f} kg/m). "
                    "Choose based on availability or connection preference."
                )

        with st.expander("Show all sections evaluated (full table)"):
            combined = pd.concat([
                pfc_results.assign(family="PFC"),
                tfc_results.assign(family="TFC"),
            ])[["family", "designation", "mass", "Cr", "util", "passes", "slenderness_ok", "is_class4", "governing"]]
            combined = combined.sort_values(["family", "mass"]).reset_index(drop=True)
            combined["Cr"]   = combined["Cr"].map(lambda x: f"{x:.1f}")
            combined["util"] = combined["util"].map(lambda x: f"{x:.2f}")
            combined["mass"] = combined["mass"].map(lambda x: f"{x:.1f}")
            combined["passes"] = combined["passes"].map(lambda x: "✅" if x else "❌")
            combined["slenderness_ok"] = combined["slenderness_ok"].map(lambda x: "OK" if x else "⚠")
            combined["is_class4"] = combined["is_class4"].map(lambda x: "Cl.4" if x else "—")
            combined["governing"] = combined["governing"].map(lambda x: "Flex-Tors" if x == "FT" else "Weak-axis")
            st.dataframe(combined, use_container_width=True, hide_index=True)